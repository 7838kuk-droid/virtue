#!/usr/bin/env python3
"""
discover_new_papers.py
======================
KCI API를 이용해 새로운 '덕 윤리' 관련 논문을 자동으로 탐색·수집하고
CSV와 대시보드(index.html)에 자동 반영하는 완전 자동화 파이프라인.

[완전 자동화 워크플로우]
  1. KCI articleSearch API로 검색어 목록을 순회하며 논문 수집
  2. 이미 데이터셋에 있는 논문 ID 제외 (중복 방지)
  3. 신규 논문만 골라 전체 메타데이터 구성
  4. 자동 카테고리 분류 (classify_audit.py 로직 재활용)
  5. CSV 파일에 새 행 추가
  6. index.html 의 __DASHBOARD_DATA__ 갱신

[사용법]
  # 기본 실행 (최근 1년 신규 논문 탐색)
  python3 discover_new_papers.py

  # 특정 연도 범위 지정
  python3 discover_new_papers.py --from-year 2025 --to-year 2026

  # 실제 저장 없이 미리보기
  python3 discover_new_papers.py --dry-run

  # 승인 없이 자동 추가 (배치 실행용)
  python3 discover_new_papers.py --auto-approve
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from collections import Counter

try:
    import requests
except ImportError:
    sys.exit("requests 모듈 필요: pip install requests")

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
API_KEY  = "78270810"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")
API_DELAY = 0.6  # 초

# KCI 검색 쿼리 목록 (이 목록을 순회하며 신규 논문 탐색)
SEARCH_QUERIES = [
    "덕 윤리",
    "덕윤리",
    "virtue ethics",
    "덕 이론",
    "덕론",
    "아레테",
    "덕성 윤리",
]

# 자동 카테고리 분류 키워드 맵
CATEGORY_KEYWORDS = {
    "비교철학적 접근": [
        "유교", "유학", "공자", "맹자", "노자", "장자", "불교", "도교", "동양",
        "비교", "정약용", "주역", "성리학", "퇴계", "율곡", "공자학", "유가",
    ],
    "교육학적 접근": [
        "도덕교육", "교육", "학교", "교사", "학생", "교육과정", "인성교육",
        "도덕 교육", "인성", "초등", "중등", "고등", "교수법",
    ],
    "신학적 접근": [
        "신학", "기독교", "가톨릭", "불교", "종교", "신앙", "하느님", "하나님",
        "그리스도", "성경", "신", "영성",
    ],
    "응용/실천 윤리": [
        "의료", "생명", "환경", "AI", "인공지능", "기술", "사회", "법",
        "경제", "비즈니스", "스포츠", "음식", "낙태", "안락사", "임상",
        "생태", "동물", "비만", "간호", "의사",
    ],
    "이론적/규범적 분석": [
        "아리스토텔레스", "플라톤", "칸트", "흄", "매킨타이어", "너스바움",
        "이론", "규범", "분석", "철학", "윤리학", "덕 개념", "덕의 본질",
        "행복", "eudaimonia", "eudaemonism",
    ],
}


# ─────────────────────────────────────────────
# KCI API
# ─────────────────────────────────────────────
def _strip_cdata(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<!\[CDATA\[|\]\]>", "", text)
    return text.strip()


def search_articles(query: str, from_year: int, to_year: int, page: int = 1) -> tuple[int, list[dict]]:
    """articleSearch API 호출. (total, records) 반환."""
    url = (
        "https://www.kci.go.kr/kciportal/po/openapi/openApiSearch.kci"
        f"?key={API_KEY}&apiCode=articleSearch"
        f"&title={requests.utils.quote(query)}"
        f"&pubYearFrom={from_year}&pubYearTo={to_year}"
        f"&page={page}&displayCount=100"
    )
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        root = ET.fromstring(res.content)

        total = int(root.findtext(".//total") or "0")
        records = []

        for rec in root.findall(".//record"):
            ji = rec.find("journalInfo")
            ai = rec.find("articleInfo")
            if ai is None:
                continue

            art_id = ai.get("article-id", "")
            if not art_id:
                continue

            # 제목
            title_ko = _strip_cdata(ai.findtext("title-group/article-title[@lang='original']") or "")
            title_en = _strip_cdata(ai.findtext("title-group/article-title[@lang='english']") or
                                    ai.findtext("title-group/article-title[@lang='foreign']") or "")

            # 저자 & 기관 (형식: "홍길동(서울대학교)")
            raw_authors = [a.text or "" for a in ai.findall("author-group/author")]
            authors, institutions = [], []
            for ra in raw_authors:
                ra = ra.strip()
                m = re.match(r"^(.+?)\((.+?)\)$", ra)
                if m:
                    authors.append(m.group(1).strip())
                    institutions.append(m.group(2).strip())
                elif ra:
                    authors.append(ra)
                    institutions.append("")

            # 초록
            abstract_ko = _strip_cdata(ai.findtext("abstract-group/abstract[@lang='original']") or
                                       ai.findtext("abstract-group/abstract[@lang='korean']") or "")
            abstract_en = _strip_cdata(ai.findtext("abstract-group/abstract[@lang='english']") or "")

            # 페이지
            fpage = ai.findtext("fpage") or ""
            lpage = ai.findtext("lpage") or ""

            # 인용수, DOI, URL
            cit_count = int(ai.findtext("citation-count") or "0")
            doi       = _strip_cdata(ai.findtext("doi") or "")
            url_link  = _strip_cdata(ai.findtext("url") or "")

            # 학술지 정보
            j_name    = (ji.findtext("journal-name") or "") if ji is not None else ""
            j_pub     = (ji.findtext("publisher-name") or "") if ji is not None else ""
            j_year    = (ji.findtext("pub-year") or "") if ji is not None else ""
            j_mon     = (ji.findtext("pub-mon") or "") if ji is not None else ""
            j_vol     = (ji.findtext("volume") or "") if ji is not None else ""
            j_issue   = (ji.findtext("issue") or "") if ji is not None else ""
            kci_reg   = (ji.findtext("kci-registration") or "등재") if ji is not None else "등재"

            # 주제분야
            subj = ai.findtext("article-categories") or ""
            lang = ai.findtext("article-language") or "한국어"

            records.append({
                "논문 ID":       art_id,
                "논문명":        title_ko,
                "영어제목":      title_en,
                "저자명":        ";".join(authors),
                "소속기관":      institutions[0] if institutions else "",
                "초록":          abstract_ko,
                "영어초록":      abstract_en,
                "발행연도":      j_year,
                "발행일":        f"{j_year}-{j_mon}" if j_mon else j_year,
                "학술지명":      j_name,
                "발행기관명":    j_pub,
                "호":            j_issue,
                "권":            j_vol,
                "시작페이지":    fpage,
                "끝페이지":      lpage,
                "인용된 총 횟수": cit_count,
                "주제분야":      subj,
                "언어":          lang,
                "등재구분":      kci_reg,
                "DOI":           doi,
                "URL":           url_link,
                "주제어":        "",  # articleSearch에는 키워드 없음 → articleDetail로 보완
            })

        return total, records

    except Exception as e:
        print(f"  ✗ 검색 오류 ({query}): {e}")
        return 0, []


def fetch_keywords_for(art_id: str) -> str:
    """articleDetail API로 키워드 가져오기."""
    url = (
        "https://www.kci.go.kr/kciportal/po/openapi/openApiSearch.kci"
        f"?key={API_KEY}&apiCode=articleDetail&id={art_id}"
    )
    try:
        res = requests.get(url, timeout=15)
        root = ET.fromstring(res.content)
        kws = [_strip_cdata(k.text or "") for k in root.findall(".//keyword-group/keyword")]
        return ",".join([k for k in kws if k])
    except Exception:
        return ""


# ─────────────────────────────────────────────
# 카테고리 자동 분류
# ─────────────────────────────────────────────
def auto_classify(paper: dict) -> list[str]:
    """제목+초록+키워드 텍스트로 카테고리 자동 분류."""
    text = " ".join([
        paper.get("논문명", ""),
        paper.get("초록", ""),
        paper.get("주제어", ""),
        paper.get("주제분야", ""),
    ]).lower()

    matched = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text:
                matched.append(cat)
                break

    return matched if matched else ["이론적/규범적 분석"]


# ─────────────────────────────────────────────
# CSV & Dashboard 유틸 (enrich_and_rebuild.py 와 공유)
# ─────────────────────────────────────────────
def load_csv(path: str) -> tuple[list[dict], list[str]]:
    if not os.path.exists(path):
        return [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def save_csv(path: str, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_dashboard_data(html_path: str) -> tuple[list[dict], int, int]:
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    marker    = "window.__DASHBOARD_DATA__ = "
    start_raw = content.find(marker)
    if start_raw == -1:
        raise ValueError("__DASHBOARD_DATA__ 를 찾을 수 없습니다.")
    arr_start = start_raw + len(marker)
    depth = 0; i = arr_start; in_str = False; esc = False
    while i < len(content):
        c = content[i]
        if esc:                    esc = False
        elif c == "\\" and in_str: esc = True
        elif c == '"' and not esc: in_str = not in_str
        elif not in_str:
            if c == "[":  depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    arr_end = i + 1; break
        i += 1
    else:
        raise ValueError("배열 끝을 찾을 수 없습니다.")
    data = json.loads(content[arr_start:arr_end])
    return data, arr_start, arr_end


def inject_dashboard_data(html_path: str, data: list[dict], arr_start: int, arr_end: int):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content[:arr_start] + new_json + content[arr_end:])


# ─────────────────────────────────────────────
# 논문 → 대시보드 포맷 변환
# ─────────────────────────────────────────────
def paper_to_dashboard_entry(paper: dict, categories: list[str]) -> dict:
    """API에서 가져온 논문 dict를 대시보드 JSON 포맷으로 변환."""
    try:
        start_p = float(paper.get("시작페이지") or 0)
        end_p   = float(paper.get("끝페이지") or 0)
    except ValueError:
        start_p, end_p = 0.0, 0.0

    try:
        pub_year = int(paper.get("발행연도") or 0)
    except ValueError:
        pub_year = 0

    cit = int(paper.get("인용된 총 횟수") or 0)

    # 키워드 정규화 (쉼표·세미콜론 분리)
    raw_kw = paper.get("주제어", "")
    kws_normalized = [k.strip() for k in re.split(r"[,;]", raw_kw) if k.strip()]

    # 소속기관 정규화 (괄호 안 지역명 제거 등)
    inst_raw = paper.get("소속기관", "") or ""
    inst_norm = re.sub(r"\s*(대학교|대학|학교)$", "대학교", inst_raw)

    # networkImpactScore 초기값
    net_score = round(cit * 1.0, 1)

    return {
        "논문명":           paper.get("논문명", ""),
        "저자명":           paper.get("저자명", ""),
        "소속기관":         inst_raw,
        "인용된 총 횟수":   cit,
        "참고문헌 수":      0,
        "발행연도":         pub_year,
        "발행일":           paper.get("발행일", ""),
        "주제분야":         paper.get("주제분야", ""),
        "URL":              paper.get("URL", ""),
        "논문 ID":          paper.get("논문 ID", ""),
        "초록":             paper.get("초록", ""),
        "주제어":           paper.get("주제어", ""),
        "영어키워드":       paper.get("영어초록", ""),   # 키워드 대용
        "학술지명":         paper.get("학술지명", ""),
        "발행기관명":       paper.get("발행기관명", ""),
        "DOI":              paper.get("DOI", ""),
        "언어":             paper.get("언어", "한국어"),
        "등재구분":         paper.get("등재구분", "등재"),
        "호":               paper.get("호"),
        "시작페이지":       start_p,
        "끝페이지":         end_p,
        "cites":            [],
        "cited_by":         [],
        "networkImpactScore": net_score,
        "citedScoreBonus":  0.0,
        "소속기관_정규화":   inst_norm,
        "키워드_정규화":     kws_normalized,
        "참고문헌_정밀분석": [],
        "categories":       categories,
        "참고문헌목록":      [],
    }


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="KCI에서 신규 덕 윤리 논문을 자동 탐색·수집합니다.")
    parser.add_argument("--from-year", type=int, default=datetime.now().year - 1,
                        help="검색 시작 연도 (기본: 작년)")
    parser.add_argument("--to-year",   type=int, default=datetime.now().year,
                        help="검색 종료 연도 (기본: 올해)")
    parser.add_argument("--dry-run",       action="store_true", help="파일 저장 없이 미리보기")
    parser.add_argument("--auto-approve",  action="store_true", help="확인 없이 자동 추가")
    args = parser.parse_args()

    print("=" * 60)
    print("  덕 윤리 대시보드 — 신규 논문 자동 탐색 파이프라인")
    print(f"  검색 연도: {args.from_year} ~ {args.to_year}")
    print("=" * 60)

    # ── 기존 데이터 로드 ─────────────────────────
    print("\n[1/5] 기존 데이터 로드 중...")
    try:
        dash_data, arr_start, arr_end = load_dashboard_data(HTML_FILE)
    except Exception as e:
        sys.exit(f"  ✗ 오류: {e}")
    existing_ids = {p.get("논문 ID") for p in dash_data if p.get("논문 ID")}
    csv_rows, csv_fields = load_csv(CSV_FILE)
    print(f"  → 기존 논문 {len(existing_ids)}편 확인")

    # ── KCI 검색 ─────────────────────────────────
    print(f"\n[2/5] KCI API 탐색 ({len(SEARCH_QUERIES)}개 검색어)...")
    all_found: dict[str, dict] = {}  # art_id → paper

    for q in SEARCH_QUERIES:
        print(f"  검색어: '{q}' ", end="", flush=True)
        total, recs = search_articles(q, args.from_year, args.to_year)
        new_count = 0
        for r in recs:
            if r["논문 ID"] not in existing_ids and r["논문 ID"] not in all_found:
                all_found[r["논문 ID"]] = r
                new_count += 1
        print(f"→ {total}건 검색, 신규 {new_count}건")
        time.sleep(API_DELAY)

    if not all_found:
        print("\n  ✔ 새로 추가할 논문이 없습니다. 데이터셋이 최신 상태입니다!")
        return

    print(f"\n  총 신규 논문 후보: {len(all_found)}편")

    # ── 키워드 보완 + 분류 ────────────────────────
    print(f"\n[3/5] 키워드 수집 및 카테고리 자동 분류...")
    new_papers_list = []
    for idx, (art_id, paper) in enumerate(all_found.items()):
        title = paper["논문명"][:45]
        print(f"  [{idx+1}/{len(all_found)}] {title}")

        # 키워드 (articleDetail에서)
        if not paper.get("주제어"):
            paper["주제어"] = fetch_keywords_for(art_id)
            time.sleep(API_DELAY)

        # 자동 분류
        cats = auto_classify(paper)
        paper["_categories"] = cats
        new_papers_list.append(paper)
        print(f"    → 분류: {cats}")

    # ── 미리보기 출력 ─────────────────────────────
    print(f"\n[4/5] 추가 예정 논문 목록:")
    print("-" * 60)
    for i, paper in enumerate(new_papers_list):
        print(f"  {i+1}. [{paper['발행연도']}] {paper['논문명'][:50]}")
        print(f"     저자: {paper['저자명']} | 학술지: {paper['학술지명']}")
        print(f"     카테고리: {paper['_categories']}")
        print(f"     초록: {'있음' if paper.get('초록') else '없음'} | 키워드: {paper.get('주제어','')[:40]}")
    print("-" * 60)

    if args.dry_run:
        print("\n  ※ dry-run 모드 — 실제 저장하지 않습니다.")
        return

    if not args.auto_approve:
        ans = input(f"\n위 {len(new_papers_list)}편을 데이터셋에 추가하시겠습니까? [y/N]: ").strip().lower()
        if ans != "y":
            print("  취소되었습니다.")
            return

    # ── 저장 ─────────────────────────────────────
    print(f"\n[5/5] 데이터 저장 중...")

    # CSV 컬럼 확인 및 추가
    new_csv_cols = ["초록", "영어초록", "주제어", "DOI", "언어", "호"]
    for col in new_csv_cols:
        if col not in csv_fields:
            csv_fields.append(col)

    added = 0
    for paper in new_papers_list:
        cats = paper.pop("_categories", ["이론적/규범적 분석"])

        # ① CSV에 추가
        csv_row = {
            "논문명":           paper["논문명"],
            "저자명":           paper["저자명"],
            "발행연도":         paper["발행연도"],
            "인용된 총 횟수":   paper["인용된 총 횟수"],
            "참고문헌 수":      "",
            "소속기관":         paper["소속기관"],
            "주제분야":         paper["주제분야"],
            "학술지명":         paper["학술지명"],
            "발행기관명":       paper["발행기관명"],
            "주제어":           paper.get("주제어", ""),
            "URL":              paper["URL"],
            "논문 ID":          paper["논문 ID"],
            "초록":             paper.get("초록", ""),
            "영어초록":         paper.get("영어초록", ""),
            "DOI":              paper.get("DOI", ""),
            "언어":             paper.get("언어", ""),
            "호":               paper.get("호", ""),
        }
        csv_rows.append(csv_row)

        # ② 대시보드 entry 추가
        entry = paper_to_dashboard_entry(paper, cats)
        dash_data.append(entry)
        added += 1

    # 저장
    save_csv(CSV_FILE, csv_rows, csv_fields)
    inject_dashboard_data(HTML_FILE, dash_data, arr_start, arr_end)

    print(f"\n  ✔ CSV에 {added}편 추가 완료")
    print(f"  ✔ index.html 갱신 완료 (총 {len(dash_data)}편)")
    print()
    print("=" * 60)
    print(f"  완료! 신규 {added}편이 대시보드에 반영되었습니다.")
    print("  → 브라우저에서 index.html 새로고침(F5) 하시면 바로 확인 가능합니다.")
    print("=" * 60)


if __name__ == "__main__":
    main()
