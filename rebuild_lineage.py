#!/usr/bin/env python3
import os
import re
import csv
import json
import time
from discover_theses import fetch_thesis_detail, search_riss_theses, load_dashboard_data, inject_dashboard_data, rebuild_network_and_scores, auto_classify, clean_institution

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")
API_DELAY = 1.0

# 1. 탑 30 저자 추출 함수
def get_top_authors(csv_path, top_n=30):
    import collections
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        authors = []
        for row in reader:
            for a in row.get('저자명', '').split(';'):
                a = a.strip()
                if a:
                    authors.append(a)
    return [x[0] for x in collections.Counter(authors).most_common(top_n)]

# 2. RISS에서 저자명으로 학위논문 검색
def find_theses_for_author(author_name):
    # 저자명 필드(bib_a) 혹은 통합검색으로 학위논문만 가져오기
    # 여기서는 discover_theses.py의 search_riss_theses 활용
    query = f"저자 {author_name}"
    # 너무 많이 나오면 문제니 20개까지만 (동명이인 등)
    return search_riss_theses(query, max_results=20, sort_order='RANK')

def main():
    print("=" * 60)
    print("  사제 관계(지도교수) 데이터 재구축 스크립트 실행")
    print("=" * 60)

    # 기존 데이터 로드
    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
        csv_fields = list(reader.fieldnames or [])

    dash_data, arr_start, arr_end = load_dashboard_data(HTML_FILE)

    top_authors = get_top_authors(CSV_FILE, top_n=30)
    print(f"  → 주요 연구자 30명: {top_authors}")

    # 1. 기존 GEN_EXT_ 데이터의 지도교수를 실제 RISS 데이터로 검증/교체
    print("\n[1/3] 기존 학위논문(GEN_EXT 포함) 지도교수 정보 실제 데이터로 정제...")
    existing_ids = {r["논문 ID"] for r in csv_rows}
    
    for row in csv_rows:
        if row.get("등재구분", "").startswith("학위논문"):
            url = row.get("URL", "")
            control_match = re.search(r'control_no=([^&]+)', url)
            if control_match:
                c_no = control_match.group(1)
                detail = fetch_thesis_detail(c_no)
                time.sleep(API_DELAY)
                if detail and detail.get('advisor'):
                    real_advisor = detail.get('advisor')
                    old_advisor = row.get("지도교수", "")
                    if old_advisor != real_advisor:
                        print(f"      수정: {row.get('논문명')} [{old_advisor} -> {real_advisor}]")
                        row["지도교수"] = real_advisor

    # 1.5. 주요 연구자 중 학위논문이 없는 경우 새로 수집
    print("\n[1.5/3] 주요 연구자 본인의 학위논문 누락분 추가 수집...")
    new_theses = []
    
    # 중복 방지를 위한 제목, 저자, 연도 키
    def make_dedup_key(title, author, year):
        t = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(title)).lower()
        a = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(author)).lower()
        y = re.sub(r"\D", "", str(year))[:4]
        return (t, a, y)
        
    existing_keys = {make_dedup_key(r.get("논문명"), r.get("저자명"), r.get("발행연도")) for r in csv_rows}
    
    for author in top_authors:
        print(f"  → '{author}' 학위논문 검색 중...")
        # 저자 조건으로 RISS 학위논문 검색
        cands = search_riss_theses(author, max_results=5, sort_order='RANK')
        for c in cands:
            # 저자명 일치 확인
            if author not in c["저자명"]:
                continue
            if c["논문 ID"] in existing_ids:
                continue
            k = make_dedup_key(c["논문명"], c["저자명"], c["발행연도"])
            if k in existing_keys:
                continue
                
            # 상세 파싱
            detail = fetch_thesis_detail(c['control_no'])
            time.sleep(API_DELAY)
            if not detail: continue
            
            degree_clean = "학위논문"
            raw_deg = c.get('degree_raw', '')
            degree_type = "석사"
            if '석사' in raw_deg:
                degree_clean = "학위논문(석사)"
                degree_type = "석사"
            elif '박사' in raw_deg:
                degree_clean = "학위논문(박사)"
                degree_type = "박사"
                
            inst_raw = c.get('소속기관') or detail.get('thesis_info') or ""
            inst_clean = clean_institution(inst_raw)
            kws = detail.get('keywords', [])
            
            abstract_ko = ""
            abstract_en = ""
            abstract_raw = detail.get('abstract', '')
            if abstract_raw:
                if re.search(r"[\uac00-\ud7a3]", abstract_raw):
                    abstract_ko = abstract_raw
                else:
                    abstract_en = abstract_raw
                    
            thesis_entry = {
                "논문명": c["논문명"],
                "저자명": c["저자명"],
                "발행연도": c["발행연도"],
                "인용된 총 횟수": 0,
                "참고문헌 수": 0,
                "소속기관": inst_raw,
                "소속기관_정규화": inst_clean,
                "주제분야": "철학/윤리학",
                "학술지명": degree_clean,
                "발행기관명": inst_raw,
                "주제어": ";".join(kws),
                "키워드_정규화": ",".join(kws),
                "URL": c["URL"],
                "논문 ID": c["논문 ID"],
                "초록": abstract_ko,
                "영어초록": abstract_en,
                "DOI": "",
                "언어": detail.get('language', '한국어'),
                "등재구분": degree_clean,
                "호": "",
                "참고문헌목록": "참고문헌데이터없음",
                "지도교수": detail.get('advisor', ''),
                "학위구분": degree_type
            }
            
            # 대시보드 데이터용 필드
            thesis_dash = thesis_entry.copy()
            thesis_dash["발행일"] = c["발행연도"]
            thesis_dash["키워드_정규화"] = kws
            thesis_dash["영어키워드"] = detail.get('english_title', '')
            thesis_dash["시작페이지"] = 0.0
            thesis_dash["끝페이지"] = 0.0
            thesis_dash["cites"] = []
            thesis_dash["cited_by"] = []
            thesis_dash["networkImpactScore"] = 0.0
            thesis_dash["citedScoreBonus"] = 0.0
            thesis_dash["참고문헌_정밀분석"] = []
            thesis_dash["categories"] = auto_classify(thesis_dash)
            
            csv_rows.append(thesis_entry)
            dash_data.append(thesis_dash)
            new_theses.append(thesis_entry)
            existing_ids.add(c["논문 ID"])
            existing_keys.add(k)
            print(f"      ✔ 신규 학위논문 추가: {c['논문명'][:20]}... (지도교수: {detail.get('advisor')})")

    # 2. 대시보드 데이터 동기화
    print("\n[2/3] 대시보드 데이터 동기화...")
    # csv_rows를 기반으로 대시보드 데이터 업데이트
    id_to_csv = {r["논문 ID"]: r for r in csv_rows}
    
    for d in dash_data:
        did = d.get("논문 ID")
        if did in id_to_csv:
            # csv에서 변경된 지도교수 덮어쓰기
            d["지도교수"] = id_to_csv[did].get("지도교수", "")

    rebuild_network_and_scores(dash_data)

    # 저장
    print("\n[3/3] 결과 저장...")
    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_rows)
        
    inject_dashboard_data(HTML_FILE, dash_data, arr_start, arr_end)
    print(f"  ✔ 완료! (장동익-황경식 등 잘못된 매핑 수정 및 {len(new_theses)}건 신규 학위논문 추가됨)")

if __name__ == "__main__":
    main()
