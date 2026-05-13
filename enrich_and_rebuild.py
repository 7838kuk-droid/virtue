#!/usr/bin/env python3
"""
enrich_and_rebuild.py
=====================
새 논문이 CSV에 추가될 때마다 실행하는 KCI API 메타데이터 보완 파이프라인.

[KCI Open API 제공 정보]
  ✔ 초록 (한국어 / 영어)
  ✔ 키워드
  ✔ 인용 횟수 (최신값)
  ✔ DOI, 학술지명, 발행연도, 언어, 호 등
  ✗ 참고문헌 목록 (Open API 미지원 → 기존 데이터 유지)

[사용법]
  # 모든 누락 논문 보완
  python3 enrich_and_rebuild.py

  # 특정 논문만 지정해서 보완
  python3 enrich_and_rebuild.py --ids ART003309398 ART003303628

  # 실제 파일 수정 없이 미리보기
  python3 enrich_and_rebuild.py --dry-run
"""

import argparse
import csv
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    sys.exit("requests 모듈이 없습니다. 'pip install requests' 를 먼저 실행해 주세요.")

# ─────────────────────────────────────────────
# 설정값
# ─────────────────────────────────────────────
API_KEY   = "78270810"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")
API_DELAY = 0.8  # 초 (KCI 과부하 방지)

# CSV에 없으면 자동으로 추가할 컬럼
EXTRA_COLUMNS = ["초록", "영어초록", "주제어", "참고문헌목록", "참고문헌 수", "DOI", "언어", "호"]

# 실제 내용이 없는 것과 동일하게 취급할 플레이스홀더 텍스트
PLACEHOLDER_TEXTS = {
    "초록 정보가 제공되지 않았습니다.",
    "초록 정보가 제공되지 않는 논문입니다.",
    "초록 없음",
    "정보 없음",
    "N/A",
    "미상",
    "없음",
}


# ─────────────────────────────────────────────
# KCI API 호출
# ─────────────────────────────────────────────
def _strip(text: str) -> str:
    return (text or "").strip()


def fetch_article_detail(article_id: str) -> dict | None:
    """KCI articleDetail API 로 논문 상세 정보를 가져온다."""
    url = (
        "https://www.kci.go.kr/kciportal/po/openapi/openApiSearch.kci"
        f"?key={API_KEY}&apiCode=articleDetail&id={article_id}"
    )
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        root = ET.fromstring(res.content)

        # API 에러 응답 확인
        err = root.findtext(".//resultMsg") or ""
        if "없음" in err or "오류" in err:
            print(f"    ⚠ API 오류 메시지: {err}")
            return None

        rec = root.find(".//record")
        if rec is None:
            return None

        ji = rec.find("journalInfo")
        ai = rec.find("articleInfo")
        if ai is None:
            return None

        # 초록
        abstract_ko = _strip(ai.findtext("abstract[@lang='original']") or
                              ai.findtext("abstract[@lang='korean']") or "")
        abstract_en = _strip(ai.findtext("abstract[@lang='english']") or "")

        # 키워드
        keywords = [_strip(k.text or "") for k in ai.findall("keyword-group/keyword")]
        keywords = [k for k in keywords if k]

        # DOI, 인용수, 학술지 정보
        doi       = _strip(ai.findtext("doi") or "")
        cit_count = _strip(ai.findtext("citation-count") or "0")
        language  = _strip(ai.findtext("article-language") or "")
        issue     = _strip((ji.findtext("issue") if ji is not None else "") or "")
        j_name    = _strip((ji.findtext("journal-name") if ji is not None else "") or "")
        j_pub     = _strip((ji.findtext("publisher-name") if ji is not None else "") or "")
        kci_reg   = _strip((ji.findtext("kci-registration") if ji is not None else "") or "")

        return {
            "초록":           abstract_ko,
            "영어초록":       abstract_en,
            "주제어":         ",".join(keywords),
            "DOI":            doi,
            "언어":           language,
            "호":             issue,
            "학술지명":       j_name,
            "발행기관명":     j_pub,
            "등재구분":       kci_reg,
            "인용된 총 횟수": cit_count,
            # 참고문헌은 API에서 미지원
        }

    except requests.RequestException as e:
        print(f"    ✗ 네트워크 오류: {e}")
        return None
    except ET.ParseError as e:
        print(f"    ✗ XML 파싱 오류: {e}")
        return None


# ─────────────────────────────────────────────
# CSV 유틸
# ─────────────────────────────────────────────
def load_csv(path: str) -> tuple[list[dict], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    # 없는 컬럼 추가
    for col in EXTRA_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)
            for row in rows:
                row.setdefault(col, "")
    return rows, fieldnames


def save_csv(path: str, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ─────────────────────────────────────────────
# Dashboard JSON 유틸
# ─────────────────────────────────────────────
def load_dashboard_data(html_path: str) -> tuple[list[dict], int, int]:
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker = "window.__DASHBOARD_DATA__ = "
    start = content.find(marker)
    if start == -1:
        raise ValueError("index.html 에서 __DASHBOARD_DATA__ 를 찾을 수 없습니다.")

    arr_start = start + len(marker)
    depth = 0; i = arr_start; in_str = False; esc = False
    while i < len(content):
        c = content[i]
        if esc:                   esc = False
        elif c == "\\" and in_str: esc = True
        elif c == '"' and not esc: in_str = not in_str
        elif not in_str:
            if c == "[":   depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    arr_end = i + 1
                    break
        i += 1
    else:
        raise ValueError("__DASHBOARD_DATA__ 배열의 끝을 찾을 수 없습니다.")

    data = json.loads(content[arr_start:arr_end])
    return data, arr_start, arr_end


def inject_dashboard_data(html_path: str, data: list[dict], arr_start: int, arr_end: int):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content[:arr_start] + new_json + content[arr_end:])


# ─────────────────────────────────────────────
# 보완 로직
# ─────────────────────────────────────────────
def _is_empty(value) -> bool:
    """값이 비어있거나 플레이스홀더 텍스트면 True."""
    if not value:
        return True
    return str(value).strip() in PLACEHOLDER_TEXTS


def needs_enrichment(paper: dict) -> bool:
    """초록이나 키워드가 없거나 플레이스홀더면 True."""
    return _is_empty(paper.get("초록")) or _is_empty(paper.get("주제어"))


def apply_api_to_paper(paper: dict, api_data: dict) -> bool:
    """api_data를 paper에 병합. 변경이 있으면 True 반환."""
    changed = False
    for field in ["초록", "영어초록", "주제어", "DOI", "언어", "호", "학술지명", "발행기관명"]:
        # 플레이스홀더 포함 빈 값이면 덮어씌움
        if _is_empty(paper.get(field)) and api_data.get(field):
            paper[field] = api_data[field]
            changed = True
    # 인용수: API 값이 더 크면 업데이트
    try:
        api_cit = int(api_data.get("인용된 총 횟수", 0))
        cur_cit = int(paper.get("인용된 총 횟수", 0))
        if api_cit > cur_cit:
            paper["인용된 총 횟수"] = api_cit
            changed = True
    except (ValueError, TypeError):
        pass
    return changed


def apply_api_to_csv_row(row: dict, api_data: dict) -> bool:
    changed = False
    for field in ["초록", "영어초록", "주제어", "DOI", "언어", "호", "학술지명", "발행기관명"]:
        if _is_empty(row.get(field)) and api_data.get(field):
            row[field] = api_data[field]
            changed = True
    try:
        api_cit = int(api_data.get("인용된 총 횟수", 0))
        cur_cit = int(row.get("인용된 총 횟수", 0))
        if api_cit > cur_cit:
            row["인용된 총 횟수"] = str(api_cit)
            changed = True
    except (ValueError, TypeError):
        pass
    return changed


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="KCI API로 논문 메타데이터를 보완하고 대시보드를 갱신합니다."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 파일 수정 없이 로그만 출력")
    parser.add_argument("--ids", nargs="*",
                        help="특정 논문 ID만 처리 (예: ART003309398 ART003303628)")
    args = parser.parse_args()

    print("=" * 60)
    print("  덕 윤리 대시보드 — KCI 데이터 보완 파이프라인")
    print("=" * 60)

    # 1. 대시보드 데이터 로드
    print("\n[1/4] index.html 데이터 로드 중...")
    try:
        dash_data, arr_start, arr_end = load_dashboard_data(HTML_FILE)
    except Exception as e:
        sys.exit(f"  ✗ 오류: {e}")
    id_to_dash_idx = {p.get("논문 ID"): i for i, p in enumerate(dash_data) if p.get("논문 ID")}
    print(f"  → {len(dash_data)}편 로드 완료")

    # 2. CSV 로드
    print("\n[2/4] CSV 파일 로드 중...")
    if os.path.exists(CSV_FILE):
        csv_rows, csv_fields = load_csv(CSV_FILE)
        id_to_csv_idx = {row.get("논문 ID", ""): i for i, row in enumerate(csv_rows) if row.get("논문 ID")}
        print(f"  → CSV {len(csv_rows)}행 로드 완료")
    else:
        print(f"  ⚠ CSV 파일 없음: {CSV_FILE}")
        csv_rows, csv_fields, id_to_csv_idx = [], [], {}

    # 3. 보완 대상 선별
    if args.ids:
        targets = [(art_id, dash_data[id_to_dash_idx[art_id]])
                   for art_id in args.ids if art_id in id_to_dash_idx]
        print(f"\n[3/4] 지정 논문 {len(targets)}편 API 조회 시작...")
    else:
        targets = [(p.get("논문 ID"), p)
                   for p in dash_data
                   if p.get("논문 ID") and needs_enrichment(p)]
        print(f"\n[3/4] 초록·키워드 누락 논문 {len(targets)}편 API 조회 시작...")

    updated_dash = 0
    updated_csv  = 0

    for idx_t, (art_id, paper) in enumerate(targets):
        title = paper.get("논문명", "?")[:50]
        print(f"\n  [{idx_t+1}/{len(targets)}] {title}")
        print(f"    ID: {art_id}")

        api_data = fetch_article_detail(art_id)
        time.sleep(API_DELAY)

        if api_data is None:
            print("    ✗ API 응답 없음 — 건너뜀")
            continue

        # 대시보드 업데이트
        d_idx = id_to_dash_idx.get(art_id)
        if d_idx is not None:
            if apply_api_to_paper(dash_data[d_idx], api_data):
                updated_dash += 1
                print(f"    ✔ 대시보드 갱신 (초록 {len(api_data.get('초록',''))}자)")
            else:
                print(f"    → 대시보드: 변경 없음")

        # CSV 업데이트
        c_idx = id_to_csv_idx.get(art_id)
        if c_idx is not None:
            if apply_api_to_csv_row(csv_rows[c_idx], api_data):
                updated_csv += 1
                print(f"    ✔ CSV 갱신")
            else:
                print(f"    → CSV: 변경 없음")

    # 4. 저장
    print(f"\n[4/4] 파일 저장 중...")
    if args.dry_run:
        print("  ※ dry-run 모드 — 실제 저장하지 않습니다.")
    else:
        if updated_dash > 0:
            inject_dashboard_data(HTML_FILE, dash_data, arr_start, arr_end)
            print(f"  ✔ index.html 저장 완료 ({updated_dash}편 갱신)")
        else:
            print("  → index.html: 변경 없음")

        if updated_csv > 0 and csv_rows:
            save_csv(CSV_FILE, csv_rows, csv_fields)
            print(f"  ✔ CSV 저장 완료 ({updated_csv}행 갱신)")
        else:
            print("  → CSV: 변경 없음")

    print()
    print("=" * 60)
    print(f"  완료! 대시보드 {updated_dash}편 / CSV {updated_csv}행 갱신됨")
    print()
    if updated_dash == 0 and len(targets) > 0:
        print("  ℹ 참고: KCI API는 초록·키워드는 제공하지만")
        print("    참고문헌 목록은 Open API로 제공되지 않습니다.")
        print("    기존 참고문헌 데이터는 이전 크롤링 결과가 유지됩니다.")
    print("=" * 60)


if __name__ == "__main__":
    main()
