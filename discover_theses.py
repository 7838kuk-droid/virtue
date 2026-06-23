#!/usr/bin/env python3
"""
discover_theses.py
==================
RISS(Academic Thesis/Dissertation) 검색 및 상세 페이지 크롤링을 수행하여
새로운 '덕 윤리' 학위논문을 수집하고 CSV와 대시보드(index.html)에 반영하는 파이프라인.

[주요 기능]
  1. RISS 학위논문 통합검색(colName=bib_t) 페이지에서 논문 정보 파싱
  2. 기 존재 데이터 중복 제거 (제목+저자+연도 및 논문 ID 기준)
  3. 신규 논문 대상 상세 페이지 파싱 (초록, 주제어, 학위유형, 지도교수 등 수집)
  4. 기존 카테고리 매핑 로직에 기반한 분류 부여
  5. CSV(virtue_ethics_final_master_cleaned.csv)에 신규 데이터 추가 (지도교수, 학위구분 필드 포함)
  6. index.html의 __DASHBOARD_DATA__ 갱신 및 전체 논문 간 인용/네트워크 영향력 재계산

[사용법]
  # 기본 실행 (RANK 기준 상위 100개 중 신규 논문 수집)
  python3 discover_theses.py

  # 인기순(VIEWCOUNT) 기준 상위 50개 수집
  python3 discover_theses.py --sort VIEWCOUNT --max-results 50

  # 실제 파일 저장 없이 미리보기
  python3 discover_theses.py --dry-run
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────────
# 설정 및 경로
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")

API_DELAY = 1.0  # RISS 차단 방지를 위한 정중한 대기 시간 (초)

# 자동 카테고리 분류 키워드
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
        "그ريس도", "성경", "신", "영성",
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

IRRELEVANT_KEYWORDS = [
    '공학', '의학', '간호', '화학', '물리', '생물', '수학', '컴퓨터', '건축', 
    '토목', '전기', '농업', '스포츠', '체육', '부동산', '경영', '마케팅', '회계', 
    '투자', '설계', '소음', '의과', '음악', '미술', '예술', '시청자', '언론', '셀룰로오스',
    '기니픽', 'Vibrio', '장신구', '초충도', '해안경관', '가상실험', '산과 염기', '가야금', 
    '의류', '패션', '생태', '농작업', '냉수침지',
    'engineering', 'medical', 'nursing', 'chemistry', 'physics', 'biology', 'math', 'computer',
    'architecture', 'civil', 'electric', 'agriculture', 'sports', 'physical', 'real estate', 'business',
    'marketing', 'accounting', 'investment', 'design', 'noise', 'art', 'music'
]

def is_irrelevant(title, inst):
    text_to_check = f"{title} {inst}".lower()
    for kw in IRRELEVANT_KEYWORDS:
        if kw.lower() in text_to_check:
            # Check if it actually contains strong ethics keywords as well
            if not any(ek in text_to_check for ek in ['윤리', '도덕', '철학', '칸트', '아리스토텔레스', '덕']):
                return True
    return False

# ─────────────────────────────────────────────
# 유틸리티 함수
# ─────────────────────────────────────────────
def clean_institution(inst_raw):
    """소속기관명에서 대학원 정보를 제거하고 정규 대학교명으로 변환."""
    if not inst_raw:
        return "소속 미상"
    # 대학교 또는 大學校 단위까지만 추출
    m = re.search(r"^(.+?(대학교|大學校))", inst_raw)
    if m:
        return m.group(1).strip()
    
    # 예비 처리
    cleaned = re.sub(r'\s*\S*대학원.*$', '', inst_raw)
    cleaned = re.sub(r'\s*\S*大學院.*$', '', cleaned)
    cleaned = re.sub(r'\s*(대학교|대학|학교|大學校|大學|學校)$', '대학교', cleaned)
    return cleaned.strip() or "소속 미상"

def make_dedup_key(title, author, year):
    """중복 체크용 정규화 키 생성."""
    t = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(title)).lower()
    a = re.sub(r"[^a-zA-Z0-9가-힣]", "", str(author)).lower()
    y = re.sub(r"\D", "", str(year))[:4]
    return (t, a, y)

def auto_classify(paper: dict) -> list[str]:
    """텍스트 매칭을 기반으로 논문 카테고리를 자동 분류."""
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
# 파일 I/O 유틸리티
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
    
    # Robust replacement: replace everything from arr_start up to the next </script>
    start_marker = "window.__DASHBOARD_DATA__ = "
    start_idx = content.find(start_marker)
    if start_idx == -1:
        start_idx = arr_start - len(start_marker)
        
    end_idx = content.find("</script>", start_idx)
    if end_idx == -1:
        end_idx = arr_end  # Fallback
        
    with open(html_path, "w", encoding="utf-8") as f:
        if content[end_idx-1] == '\n':
            # keep existing formatting if possible
            f.write(content[:start_idx + len(start_marker)] + new_json + ";\n" + content[end_idx:])
        else:
            f.write(content[:start_idx + len(start_marker)] + new_json + ";\n  " + content[end_idx:])

# ─────────────────────────────────────────────
# RISS 크롤러 엔진
# ─────────────────────────────────────────────
def search_riss_theses(query, max_results=100, sort_order='RANK'):
    """RISS에서 학위논문 목록을 검색하여 기본 정보를 수집합니다."""
    search_url = 'https://www.riss.kr/search/Search.do'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    results = []
    start_count = 0
    
    print(f"  → RISS 학위논문 검색 시작 (검색어: '{query}', 정렬: {sort_order}, 목표 수: {max_results})")
    
    while len(results) < max_results:
        params = {
            'query': query,
            'colName': 'bib_t',
            'isDetailSearch': 'N',
            'searchGubun': 'true',
            'viewYn': 'OP',
            'strSort': sort_order,
            'iStartCount': start_count
        }
        try:
            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"    ✗ 검색 페이지 로드 실패 (status: {response.status_code})")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('div', class_='cont ml60')
            if not items:
                print("    ℹ 더 이상 검색 결과가 없습니다.")
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
                
                if not is_irrelevant(title_text, assigned):
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
                else:
                    print(f"    [동명이인/무관필터 스킵] {title_text[:30]} ({assigned})")
                
                
            print(f"    수집중... ({len(results)} / {max_results})")
            start_count += 10
            time.sleep(API_DELAY)
            
        except Exception as e:
            print(f"    ✗ RISS 검색 중 오류 발생: {e}")
            break
            
    return results

def fetch_thesis_detail(control_no):
    """RISS 학위논문 상세 정보를 파싱합니다."""
    detail_url = "https://www.riss.kr/search/detail/DetailView.do"
    params = {
        'p_mat_type': 'be54d9b8bc7cdb09',
        'control_no': control_no
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
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
                label = span.text.strip()
                val = div.text.strip().replace('\n', ' ').replace('\t', ' ')
                metadata[label] = val
                
        # 지도교수 추출 (사제 관계 규명용 핵심 아이디어 구현)
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
        print(f"    ✗ {control_no} 상세정보 파싱 에러: {e}")
        return None

# ─────────────────────────────────────────────
# 데이터 병합 및 재계산 파이프라인
# ─────────────────────────────────────────────
def rebuild_network_and_scores(all_data):
    """전체 데이터셋 대상 참고문헌 교차 인용 네트워크 및 네트워크 영향력 지수를 재계산합니다."""
    print("  → 학술지 및 학위논문 간 교차 참조 네트워크 재계산 중...")
    for item in all_data:
        item['clean_title'] = str(item.get('논문명', '')).strip()
        item['cites'] = []
        item['cited_by'] = []
        item['base_cites'] = 0
        try:
            item['base_cites'] = int(item.get('인용된 총 횟수', 0))
        except:
            pass
            
    # 제목 매칭을 통한 교차 참조 생성
    for a in all_data:
        ref_text = str(a.get('참고문헌목록', '')).replace(' ', '')
        if ref_text and len(ref_text) > 5 and ref_text != 'None' and '참고문헌데이터없음' not in ref_text:
            for b in all_data:
                if a['논문 ID'] == b['논문 ID']:
                    continue
                t = b['clean_title'].replace(' ', '')
                if len(t) > 6 and t in ref_text:  # 짧은 제목 오인 매칭 방지 (6자 이상)
                    a['cites'].append(b['논문 ID'])
                    b['cited_by'].append(a['논문 ID'])
                    
    # 네트워크 영향력 지수 및 보너스 계산
    for a in all_data:
        cited_score = 0
        for b_id in a['cites']:
            b = next((x for x in all_data if x['논문 ID'] == b_id), None)
            if b:
                cited_score += b['base_cites']
        a['networkImpactScore'] = round(a['base_cites'] + (cited_score * 0.2), 1)
        a['citedScoreBonus'] = round(cited_score * 0.2, 1)
        
    # 임시 필드 일괄 제거 (KeyError 버그 수정본)
    for a in all_data:
        if 'clean_title' in a:
            del a['clean_title']
        if 'base_cites' in a:
            del a['base_cites']

# ─────────────────────────────────────────────
# 메인 제어 루프
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="RISS에서 학위논문을 수집하고 대시보드 데이터셋에 통합합니다.")
    parser.add_argument("--query", type=str, default="덕 윤리", help="검색 쿼리 (기본: '덕 윤리')")
    parser.add_argument("--max-results", type=int, default=100, help="수집할 최대 학위논문 수 (기본: 100)")
    parser.add_argument("--sort", type=str, default="RANK", choices=["RANK", "DATE", "VIEWCOUNT"], help="RISS 정렬 방식")
    parser.add_argument("--dry-run", action="store_true", help="파일을 수정하지 않고 로그만 출력")
    parser.add_argument("--auto-approve", action="store_true", help="수집 후 사용자 승인 단계를 생략하고 자동 병합")
    args = parser.parse_args()

    print("=" * 60)
    print("  덕 윤리 대시보드 — RISS 학위논문 통합 파이프라인 (사제 관계 수집 지원)")
    print("=" * 60)

    # 1. 기존 데이터 및 중복 제거용 집합 구성
    print("\n[1/5] 기존 데이터 로드 중...")
    try:
        dash_data, arr_start, arr_end = load_dashboard_data(HTML_FILE)
        print(f"  → 대시보드({HTML_FILE}): {len(dash_data)}편 확인")
    except Exception as e:
        sys.exit(f"  ✗ 대시보드 로드 오류: {e}")
        
    csv_rows, csv_fields = load_csv(CSV_FILE)
    print(f"  → CSV({CSV_FILE}): {len(csv_rows)}행 확인")

    # 중복 감지 맵
    existing_ids = {p.get("논문 ID") for p in dash_data if p.get("논문 ID")}
    existing_keys = set()
    for p in dash_data:
        k = make_dedup_key(p.get("논문명"), p.get("저자명"), p.get("발행연도"))
        existing_keys.add(k)
        
    print(f"  → 고유 메타데이터 키 {len(existing_keys)}개 캐싱 완료")

    # 2. RISS 검색 수행
    print("\n[2/5] RISS 학위논문 검색 결과 스캔 중...")
    candidates = search_riss_theses(args.query, max_results=args.max_results, sort_order=args.sort)
    
    # 중복 및 기수집 항목 사전 필터링
    new_candidates = []
    for c in candidates:
        if c["논문 ID"] in existing_ids:
            continue
        k = make_dedup_key(c["논문명"], c["저자명"], c["발행연도"])
        if k in existing_keys:
            continue
        new_candidates.append(c)
        
    print(f"  → 검색 대상 {len(candidates)}편 중 미수집 신규 후보: {len(new_candidates)}편")
    
    if not new_candidates:
        print("\n  ✔ 새로 수집할 신규 학위논문이 없습니다. 데이터셋이 최신입니다!")
        return

    # 3. 상세 정보 파싱
    print("\n[3/5] 신규 학위논문 상세 데이터 수집 및 정규화...")
    new_theses_list = []
    
    for idx, cand in enumerate(new_candidates):
        title_trunc = cand['논문명'][:40]
        print(f"  [{idx+1}/{len(new_candidates)}] '{title_trunc}...' 상세 로딩...")
        
        detail = fetch_thesis_detail(cand['control_no'])
        time.sleep(API_DELAY)
        
        if not detail:
            print("    ✗ 상세정보 수집 실패. 건너뜁니다.")
            continue
            
        # 학위 수준 판정 (석사 / 박사)
        degree_clean = "학위논문"
        raw_deg = cand.get('degree_raw', '')
        degree_type = "석사"
        if '석사' in raw_deg:
            degree_clean = "학위논문(석사)"
            degree_type = "석사"
        elif '박사' in raw_deg:
            degree_clean = "학위논문(박사)"
            degree_type = "박사"
            
        # 초록 언어 분류 및 배치
        abstract_ko = ""
        abstract_en = ""
        abstract_raw = detail.get('abstract', '')
        if abstract_raw:
            if re.search(r"[\uac00-\ud7a3]", abstract_raw):
                abstract_ko = abstract_raw
            else:
                abstract_en = abstract_raw
                
        # 발행기관 추출 및 클렌징
        inst_raw = cand.get('소속기관') or detail.get('thesis_info') or ""
        inst_clean = clean_institution(inst_raw)
        
        # 키워드 정규화
        kws = detail.get('keywords', [])
        
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
            # 사제 관계 규명용 학위 정보 및 지도교수 데이터 추가
            "지도교수": detail.get('advisor', ''),
            "학위구분": degree_type,
        }
        
        # 카테고리 자동 분류 적용
        cats = auto_classify(thesis_entry)
        thesis_entry["categories"] = cats
        
        new_theses_list.append(thesis_entry)
        print(f"    ✔ 수집 성공! (저자: {cand['저자명']} | 지도교수: {detail.get('advisor', '없음')} | 학교: {inst_clean} | 학위: {degree_type})")

    if not new_theses_list:
        print("\n  ⚠ 신규 수집된 논문이 없습니다.")
        return

    # 4. 미리보기 출력 및 사용자 승인
    print(f"\n[4/5] 병합 예정 학위논문 목록 ({len(new_theses_list)}편):")
    print("-" * 70)
    for idx, t in enumerate(new_theses_list):
        print(f"  {idx+1:02d}. [{t['발행연도']} | {t['등재구분']}] {t['논문명'][:45]}...")
        print(f"      저자: {t['저자명']} | 지도교수: {t['지도교수'] or '미확인'} | 학교: {t['소속기관_정규화']} | 카테고리: {t['categories']}")
    print("-" * 70)

    if args.dry_run:
        print("\n  ※ dry-run 모드 — 파일에 데이터를 기록하지 않고 종료합니다.")
        return

    if not args.auto_approve:
        ans = input(f"\n위 {len(new_theses_list)}편을 데이터셋에 통합하시겠습니까? [y/N]: ").strip().lower()
        if ans != 'y':
            print("  취소되었습니다.")
            return

    # 5. 저장 및 네트워크 재빌드
    print("\n[5/5] 데이터 병합 및 대시보드 빌드 중...")
    
    # CSV에 새 행 추가 및 컬럼 보존
    new_csv_fields = csv_fields.copy()
    for col in ["소속기관_정규화", "키워드_정규화", "초록", "영어초록", "주제어", "DOI", "언어", "호", "등재구분", "지도교수", "학위구분"]:
        if col not in new_csv_fields:
            new_csv_fields.append(col)
            
    for t in new_theses_list:
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
        
    # 대시보드 데이터 병합
    dash_data.extend(new_theses_list)
    
    # 인용 네트워크 재계산 (Journal <-> Thesis 모두 반영)
    rebuild_network_and_scores(dash_data)
    
    # 파일 쓰기
    save_csv(CSV_FILE, csv_rows, new_csv_fields)
    print(f"  ✔ CSV 파일 저장 완료: {CSV_FILE} (총 {len(csv_rows)}행)")
    
    inject_dashboard_data(HTML_FILE, dash_data, arr_start, arr_end)
    print(f"  ✔ index.html 파일 데이터 주입 완료 (총 {len(dash_data)}편)")
    
    print("\n" + "=" * 60)
    print(f"  통합 완료! {len(new_theses_list)}편의 학위논문이 성공적으로 데이터셋에 머지되었습니다.")
    print("  → 대시보드 index.html을 새로고침하여 바뀐 결과를 바로 확인할 수 있습니다.")
    print("=" * 60)

if __name__ == "__main__":
    main()
