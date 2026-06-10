#!/usr/bin/env python3
"""
discover_by_advisors.py
=======================
주요 덕 윤리 학자(지도교수)들을 대상으로 RISS 학위논문을 수집하여
사제 관계(학맥) 데이터셋을 구축하고 대시보드와 CSV를 갱신합니다.
"""

import os
import re
import sys
import time
import json
import csv
import requests
from bs4 import BeautifulSoup

# discover_theses.py의 핵심 함수 및 설정 로드
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")

API_DELAY = 1.0

# 대상 핵심 지도교수 리스트
TARGET_ADVISORS = [
    "황경식", "김형철", "박정순", "엄성우", "이좌용", 
    "안옥선", "문시영", "노영란", "이창호", "김대군"
]

CATEGORY_KEYWORDS = {
    "비교철학적 접근": ["유교", "유학", "공자", "맹자", "노자", "장자", "불교", "도교", "동양", "비교", "정약용", "주역", "성리학", "퇴계", "율곡", "공자학", "유가"],
    "교육학적 접근": ["도덕교육", "교육", "학교", "교사", "학생", "교육과정", "인성교육", "도덕 교육", "인성", "초등", "중등", "고등", "교수법"],
    "신학적 접근": ["신학", "기독교", "가톨릭", "불교", "종교", "신앙", "하느님", "하나님", "그리스도", "성경", "신", "영성"],
    "응용/실천 윤리": ["의료", "생명", "환경", "AI", "인공지능", "기술", "사회", "법", "경제", "비즈니스", "스포츠", "음식", "낙태", "안락사", "임상", "생태", "동물", "비만", "간호", "의사"],
    "이론적/규범적 분석": ["아리스토텔레스", "플라톤", "칸트", "흄", "매킨타이어", "너스바움", "이론", "규범", "분석", "철학", "윤리학", "덕 개념", "덕의 본질", "행복", "eudaimonia", "eudaemonism"]
}

def clean_institution(inst_raw):
    if not inst_raw:
        return "소속 미상"
    m = re.search(r"^(.+?(대학교|大學校))", inst_raw)
    if m:
        return m.group(1).strip()
    cleaned = re.sub(r'\s*\S*대학원.*$', '', inst_raw)
    cleaned = re.sub(r'\s*\S*大學院.*$', '', cleaned)
    cleaned = re.sub(r'\s*(대학교|대학|학교|大學校|大學|學校)$', '대학교', cleaned)
    return cleaned.strip() or "소속 미상"

def make_dedup_key(title, author, year):
    t = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(title)).lower()
    a = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(author)).lower()
    y = re.sub(r"\D", "", str(year))[:4]
    return (t, a, y)

def auto_classify(paper: dict) -> list[str]:
    text = " ".join([paper.get("논문명", ""), paper.get("초록", ""), paper.get("주제어", ""), paper.get("주제분야", "")]).lower()
    matched = []
    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in text:
                matched.append(cat)
                break
    return matched if matched else ["이론적/규범적 분석"]

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
    marker = "window.__DASHBOARD_DATA__ = "
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

def search_riss_by_advisor(advisor_name, max_results=20):
    """특정 교수의 이름이 들어간 학위논문을 검색합니다."""
    search_url = 'https://www.riss.kr/search/Search.do'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    results = []
    start_count = 0
    
    # RISS 검색에서 지도교수명 및 키워드로 검색 조합
    query_str = f"지도교수 {advisor_name}"
    print(f"  → RISS 학위논문 검색 시작 (교수명: '{advisor_name}', 목표 수: {max_results})")
    
    while len(results) < max_results:
        params = {
            'query': query_str,
            'colName': 'bib_t',
            'isDetailSearch': 'N',
            'searchGubun': 'true',
            'viewYn': 'OP',
            'strSort': 'RANK',
            'iStartCount': start_count
        }
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('div', class_='cont ml60')
            if not items:
                break
                
            for item in items:
                if len(results) >= max_results:
                    break
                    
                title_a = item.find('p', class_='title').find('a')
                title_text = title_a.text.strip()
                title_text = re.sub(r'\s*한글로보기\s*', '', title_text)
                
                href = title_a['href']
                control_no_match = re.search(r'control_no=([^&]+)', href)
                if not control_no_match:
                    continue
                control_no = control_no_match.group(1)
                
                # 기본 정보 추출
                etc_span = item.find('p', class_='etc')
                writer = ""
                assigned = ""
                year = ""
                degree = ""
                
                if etc_span:
                    spans = etc_span.find_all('span')
                    writer_span = etc_span.find('span', class_='writer')
                    if writer_span:
                        writer = writer_span.text.strip()
                    assigned_span = etc_span.find('span', class_='assigned')
                    if assigned_span:
                        assigned = assigned_span.text.strip()
                        
                    other_spans = [s.text.strip() for s in spans if s not in (writer_span, assigned_span)]
                    if len(other_spans) >= 1:
                        year = re.sub(r"\D", "", other_spans[0])[:4]
                    if len(other_spans) >= 2:
                        degree = other_spans[1]
                
                results.append({
                    '논문 ID': f"RISS_{control_no}",
                    '논문명': title_text,
                    '저자명': writer,
                    '소속기관': assigned,
                    '발행연도': year,
                    'degree_raw': degree,
                    'URL': "https://www.riss.kr/search/detail/DetailView.do?p_mat_type=be54d9b8bc7cdb09&control_no=" + control_no,
                    'control_no': control_no
                })
                
            start_count += 10
            time.sleep(API_DELAY)
            
        except Exception as e:
            print(f"    ✗ 검색 중 오류 발생: {e}")
            break
            
    return results

def fetch_thesis_detail(control_no):
    detail_url = "https://www.riss.kr/search/detail/DetailView.do"
    params = {'p_mat_type': 'be54d9b8bc7cdb09', 'control_no': control_no}
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0.0.0'}
    
    try:
        response = requests.get(detail_url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        metadata = {}
        for li in soup.find_all('li'):
            span = li.find('span', class_='strong')
            div = li.find('div')
            if span and div:
                metadata[span.text.strip()] = div.text.strip().replace('\n', ' ').replace('\t', ' ')
                
        # 지도교수 정밀 추출
        advisor = ""
        for k, v in metadata.items():
            if '지도' in k and '교수' in k:
                advisor = v.strip()
                advisor = re.sub(r"\s*[\(\[].*?[\)\]]", "", advisor)
                advisor = re.sub(r"\s*(교수|지도교수)$", "", advisor)
                advisor = advisor.strip()
                break
        
        if not advisor:
            for v in metadata.values():
                m = re.search(r'지도교수\s*:\s*([가-힣]{2,4})(?=(?:참고|학위|일반|주기|소장|발행|dDC|$|\s|[a-zA-Z]))', v)
                if m:
                    advisor = m.group(1).strip()
                    break
                    
        # 초록 파싱
        abstract = ''
        add_info = soup.find('div', class_='additionalInfo')
        if add_info:
            wrap = add_info.find('div', class_='textWrap')
            if wrap:
                abstract = wrap.text.strip()
                
        # 키워드 파싱
        keywords = []
        kw_li = None
        for li in soup.find_all('li'):
            span = li.find('span', class_='strong')
            if span and '주제어' in span.text:
                kw_li = li
                break
        if kw_li:
            keywords = [a.text.strip() for a in kw_li.find_all('a') if a.text.strip()]
            
        return {
            'abstract': abstract,
            'keywords': keywords,
            'english_title': metadata.get('기타서명', ''),
            'language': metadata.get('작성언어', '한국어'),
            'institution_pub': metadata.get('발행사항', ''),
            'thesis_info': metadata.get('학위논문사항', ''),
            'advisor': advisor
        }
    except Exception as e:
        return None

def rebuild_network_and_scores(all_data):
    for item in all_data:
        item['clean_title'] = str(item.get('논문명', '')).strip()
        item['cites'] = []
        item['cited_by'] = []
        item['base_cites'] = 0
        try:
            item['base_cites'] = int(item.get('인용된 총 횟수', 0))
        except:
            pass
            
    for a in all_data:
        ref_text = str(a.get('참고문헌목록', '')).replace(' ', '')
        if ref_text and len(ref_text) > 5 and ref_text != 'None' and '참고문헌데이터없음' not in ref_text:
            for b in all_data:
                if a['논문 ID'] == b['논문 ID']:
                    continue
                t = b['clean_title'].replace(' ', '')
                if len(t) > 6 and t in ref_text:
                    a['cites'].append(b['논문 ID'])
                    b['cited_by'].append(a['논문 ID'])
                    
    for a in all_data:
        cited_score = 0
        for b_id in a['cites']:
            b = next((x for x in all_data if x['논문 ID'] == b_id), None)
            if b:
                cited_score += b['base_cites']
        a['networkImpactScore'] = round(a['base_cites'] + (cited_score * 0.2), 1)
        a['citedScoreBonus'] = round(cited_score * 0.2, 1)
        
    for a in all_data:
        if 'clean_title' in a:
            del a['clean_title']
        if 'base_cites' in a:
            del a['base_cites']

def main():
    print("=" * 60)
    print("  덕 윤리 학맥 계보 타겟 수집기 (지도교수 기반)")
    print("=" * 60)
    
    # 1. 데이터 로드
    try:
        dash_data, arr_start, arr_end = load_dashboard_data(HTML_FILE)
        print(f"  → 기존 대시보드 데이터: {len(dash_data)}편")
    except Exception as e:
        sys.exit(f"  ✗ 대시보드 로드 오류: {e}")
        
    csv_rows, csv_fields = load_csv(CSV_FILE)
    print(f"  → 기존 CSV 데이터: {len(csv_rows)}행")
    
    existing_ids = {p.get("논문 ID") for p in dash_data if p.get("논문 ID")}
    existing_keys = set()
    for p in dash_data:
        k = make_dedup_key(p.get("논문명"), p.get("저자명"), p.get("발행연도"))
        existing_keys.add(k)
        
    collected_theses = []
    
    # 2. 지도교수별로 차례대로 수집
    for advisor in TARGET_ADVISORS:
        print(f"\n[대상 지도교수: {advisor}]")
        candidates = search_riss_by_advisor(advisor, max_results=10)
        
        # 필터링
        new_candidates = []
        for c in candidates:
            if c["논문 ID"] in existing_ids:
                continue
            k = make_dedup_key(c["논문명"], c["저자명"], c["발행연도"])
            if k in existing_keys:
                continue
            new_candidates.append(c)
            
        print(f"  → 미수집 신규 논문 후보: {len(new_candidates)}편")
        
        for idx, cand in enumerate(new_candidates):
            print(f"    [{idx+1}/{len(new_candidates)}] 상세 로딩: {cand['논문명'][:30]}...")
            detail = fetch_thesis_detail(cand['control_no'])
            time.sleep(API_DELAY)
            
            if not detail:
                continue
                
            # 지도교수 최종 매칭 검사 (동음이의어 또는 단순 본문 매칭 방지)
            parsed_adv = detail.get('advisor', '')
            if advisor not in parsed_adv:
                print(f"      ✗ 지도교수 불일치 (검색 대상: {advisor} | 파싱값: {parsed_adv}) - 스킵")
                continue
                
            # 학위구분
            degree_clean = "학위논문"
            raw_deg = cand.get('degree_raw', '')
            degree_type = "석사"
            if '석사' in raw_deg:
                degree_clean = "학위논문(석사)"
                degree_type = "석사"
            elif '박사' in raw_deg:
                degree_clean = "학위논문(박사)"
                degree_type = "박사"
                
            inst_raw = cand.get('소속기관') or detail.get('thesis_info') or ""
            inst_clean = clean_institution(inst_raw)
            kws = detail.get('keywords', [])
            
            # 초록
            abstract_ko = ""
            abstract_en = ""
            abstract_raw = detail.get('abstract', '')
            if abstract_raw:
                if re.search(r"[\uac00-\ud7a3]", abstract_raw):
                    abstract_ko = abstract_raw
                else:
                    abstract_en = abstract_raw
                    
            thesis_entry = {
                "논문 ID": cand["논문 ID"],
                "논문명": cand["논문명"],
                "저자명": cand["저자명"],
                "소속기관": inst_raw,
                "소속기관_정규화": inst_clean,
                "발행연도": cand["발행연도"],
                "발행일": cand["발행연도"],
                "인용된 총 횟수": 0,
                "참고문헌 수": 0,
                "주제분야": "철학/윤리학",
                "URL": cand["URL"],
                "초록": abstract_ko,
                "영어초록": abstract_en,
                "주제어": ";".join(kws),
                "키워드_정규화": kws,
                "영어키워드": detail.get('english_title', ''),
                "학술지명": degree_clean,
                "발행기관명": inst_raw,
                "DOI": "",
                "언어": detail.get('language', '한국어'),
                "등재구분": degree_clean,
                "호": "",
                "시작페이지": 0.0,
                "끝페이지": 0.0,
                "cites": [],
                "cited_by": [],
                "networkImpactScore": 0.0,
                "citedScoreBonus": 0.0,
                "참고문헌_정밀분석": [],
                "참고문헌목록": "참고문헌데이터없음",
                "지도교수": parsed_adv,
                "학위구분": degree_type,
            }
            
            cats = auto_classify(thesis_entry)
            thesis_entry["categories"] = cats
            
            collected_theses.append(thesis_entry)
            print(f"      ✔ 추가 성공! 저자: {cand['저자명']} | 소속: {inst_clean} | 학위: {degree_type}")
            
    if not collected_theses:
        print("\n  ✔ 새로 수집된 학위논문이 없습니다.")
        return
        
    print(f"\n[결과] 총 {len(collected_theses)}편의 지도교수 매칭 신규 학위논문 수집 완료.")
    
    # 3. 마스터 파일들 병합 및 빌드
    new_csv_fields = csv_fields.copy()
    for col in ["소속기관_정규화", "키워드_정규화", "초록", "영어초록", "주제어", "DOI", "언어", "호", "등재구분", "지도교수", "학위구분"]:
        if col not in new_csv_fields:
            new_csv_fields.append(col)
            
    for t in collected_theses:
        csv_row = {
            "논문명": t["논문명"],
            "저자명": t["저자명"],
            "발행연도": t["발행연도"],
            "인용된 총 횟수": t["인용된 총 횟수"],
            "참고문헌 수": t["참고문헌 수"],
            "소속기관": t["소속기관"],
            "소속기관_정규화": t["소속기관_정규화"],
            "주제분야": t["주제분야"],
            "학술지명": t["학술지명"],
            "발행기관명": t["발행기관명"],
            "주제어": t["주제어"],
            "키워드_정규화": ",".join(t["키워드_정규화"]),
            "URL": t["URL"],
            "논문 ID": t["논문 ID"],
            "초록": t["초록"],
            "영어초록": t["영어초록"],
            "DOI": t["DOI"],
            "언어": t["언어"],
            "등재구분": t["등재구분"],
            "호": t["호"],
            "참고문헌목록": t["참고문헌목록"],
            "지도교수": t["지도교수"],
            "학위구분": t["학위구분"]
        }
        csv_rows.append(csv_row)
        
    dash_data.extend(collected_theses)
    rebuild_network_and_scores(dash_data)
    
    # 파일 쓰기
    save_csv(CSV_FILE, csv_rows, new_csv_fields)
    print(f"  ✔ CSV 파일 저장 완료: {CSV_FILE} (총 {len(csv_rows)}행)")
    
    inject_dashboard_data(HTML_FILE, dash_data, arr_start, arr_end)
    print(f"  ✔ index.html 파일 데이터 주입 완료 (총 {len(dash_data)}편)")
    
    print("\n" + "=" * 60)
    print(f"  학맥 타겟 통합 완료! {len(collected_theses)}편이 성공적으로 데이터셋에 머지되었습니다.")
    print("=" * 60)

if __name__ == "__main__":
    main()
