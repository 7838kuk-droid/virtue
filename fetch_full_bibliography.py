import os
import csv
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
OUT_JSON = os.path.join(BASE_DIR, "author_full_bibliography.json")

API_DELAY = 1.0

def clean_adv(name):
    if not name: return ""
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", name).replace("교수", "").strip()


def is_relevant(paper):
    title = paper.get('title', '').lower()
    journal = paper.get('journal', '').lower()
    inst = paper.get('institution', '').lower()
    text = (title + " " + journal + " " + inst).replace(" ", "")
    
    MUST_HAVE_KEYWORDS = ['철학', '윤리', '도덕', 'philosophy', 'ethic', 'moral', 'virtue']
    for kw in MUST_HAVE_KEYWORDS:
        if kw in text:
            return True
            
    IRRELEVANT_KEYWORDS = [
        '공학', '의학', '간호', '화학', '물리', '생물', '수학', '컴퓨터', '건축', 
        '토목', '전기', '농업', '스포츠', '체육', '부동산', '경영', '마케팅', '회계', '투자', '설계', '소음', '의과',
        'engineering', 'medical', 'nursing', 'chemistry', 'physics', 'biology', 'math', 'computer',
        'architecture', 'civil', 'electric', 'agriculture', 'sports', 'physical', 'real estate', 'business',
        'marketing', 'accounting', 'investment', 'design', 'noise', 'medical'
    ]
    for kw in IRRELEVANT_KEYWORDS:
        if kw in journal or kw in inst or kw in title:
            return False
            
    RELEVANT_KEYWORDS = [
        '교육', '인문', '신학', '종교', '법학', '정치', '사회', '문화', '역사', 
        '가치', '사상', '교양', '인성', '정의', '시민', '민주', '페미니즘', '생명', '행정',
        'education', 'humanit', 'theology', 'religion', 'law', 'politic', 'society', 'social', 'culture',
        'history', 'value', 'thought', 'liberal', 'character', 'justice', 'citizen', 'democra', 'feminism', 'life', 'admin'
    ]
    for kw in RELEVANT_KEYWORDS:
        if kw in text:
            return True
            
    return False

def search_riss_author(author_name, max_results=500):
    search_url = 'https://www.riss.kr/search/Search.do'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    results = []
    
    colNames = ['re_a_kor', 'bib_t', 'bib_m', 're_a_over', 'f_thesis']
    
    for col in colNames:
        start_count = 0
        print(f"  → RISS 검색 (저자: '{author_name}', 타입: {col})")
        while len(results) < max_results:
            params = {
                'query': author_name,
                'colName': col,
                'isDetailSearch': 'N',
                'searchGubun': 'true',
                'viewYn': 'OP',
                'strSort': 'DATE',
                'iStartCount': start_count,
                'pageScale': 100
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
                    title_a = item.find('p', class_='title').find('a')
                    title_text = title_a.text.strip().replace('한글로보기', '').strip()
                    
                    etc_span = item.find('p', class_='etc')
                    writer = ""
                    assigned = ""
                    year = ""
                    journal = ""
                    
                    if etc_span:
                        writer_span = etc_span.find('span', class_='writer')
                        if writer_span:
                            writer = writer_span.text.strip()
                            
                        assigned_span = etc_span.find('span', class_='assigned')
                        if assigned_span:
                            assigned = assigned_span.text.strip()
                            
                        spans = etc_span.find_all('span')
                        other_spans = [s.text.strip() for s in spans if s not in (writer_span, assigned_span)]
                        if len(other_spans) >= 1:
                            year = re.sub(r"\D", "", other_spans[0])[:4]
                        if len(other_spans) >= 2:
                            journal = other_spans[1]
                    
                    # Exact or partial match for author name
                    # (since RISS might return papers where this author is a co-author)
                    if author_name not in writer:
                        continue
                        
                    paper_type = '학위논문' if col in ['bib_t', 'f_thesis'] else '학술논문'
                    if col == 'bib_m':
                        paper_type = '단행본'
                        
                    paper_obj = {
                        'title': title_text,
                        'authors': writer,
                        'institution': assigned,
                        'year': year,
                        'journal': journal,
                        'type': paper_type
                    }
                    if is_relevant(paper_obj):
                        results.append(paper_obj)
                    
                if len(items) < 100:
                    break # No more pages
                    
                start_count += 100
                time.sleep(API_DELAY)
                
            except Exception as e:
                print(f"    ✗ 오류: {e}")
                break
                
    # Deduplicate
    unique_results = []
    seen = set()
    for r in results:
        k = (r['title'], r['year'])
        if k not in seen:
            seen.add(k)
            unique_results.append(r)
            
    # Sort by year desc
    unique_results.sort(key=lambda x: x['year'], reverse=True)
    return unique_results[:max_results]

def main():
    print("="*50)
    print("Fetching Full Bibliography for Major Researchers")
    print("="*50)
    
    # 1. Load CSV and identify major researchers
    authors_counter = Counter()
    advisors_counter = Counter()
    student_to_adv = {}
    
    genealogy_researchers = set()
    
    with open(CSV_FILE, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            adv = clean_adv(row.get('지도교수', ''))
            is_overseas = row.get('해외_학맥_여부', 'False') == 'True'
            
            raw_authors = row.get('저자명', '').replace(';', ',').replace('/', ',')
            authors = [a.strip() for a in raw_authors.split(',') if a.strip() and a.strip() != '연구자 없음']
            
            # If there is an advisor, this paper is part of the genealogy.
            # We want to add ALL advisors and students (domestic + overseas)
            if adv and adv != 'None' and adv != '참고문헌데이터없음':
                genealogy_researchers.add(adv)
                
                # Add students
                for a in authors:
                    if clean_adv(a) != adv:
                        genealogy_researchers.add(clean_adv(a))
    
    # Filter out empty or invalid names
    major_researchers = [m for m in genealogy_researchers if m and len(m) >= 2]
    
    print(f"Identified {len(major_researchers)} domestic researchers from genealogy: {', '.join(major_researchers[:10])}...")
    
    # Check if we already have some data
    all_data = {}
    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
            
    count = 0
    # Sort them alphabetically just for consistent output
    targets = sorted(major_researchers)
    
    for author in targets:
        if author in all_data and len(all_data[author]) > 0:
            print(f"Skipping {author}, already fetched {len(all_data[author])} papers.")
            continue
            
        print(f"Fetching for: {author}")
        papers = search_riss_author(author, max_results=500) # get up to 500 recent papers per author to get all
        all_data[author] = papers
        count += 1
        
        # save incrementally
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
            
    print(f"Finished. Saved {len(all_data)} authors' bibliographies to {OUT_JSON}.")

if __name__ == "__main__":
    main()
