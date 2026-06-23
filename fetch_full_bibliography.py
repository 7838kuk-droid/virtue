import os
import csv
import json
import re
import time
import requests
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE  = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
OUT_JSON = os.path.join(BASE_DIR, "author_full_bibliography.json")

API_KEY = "78270810"
API_DELAY = 0.5

def clean_adv(name):
    if not name: return ""
    return re.sub(r"\s*[\(\[].*?[\)\]]", "", name).replace("교수", "").strip()

def _strip_cdata(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<!\[CDATA\[|\]\]>", "", text).strip()

def is_relevant(paper, author_name, known_institutions):
    title = paper.get('title', '').lower()
    journal = paper.get('journal', '').lower()
    inst = paper.get('institution', '').lower()
    
    # 1. Institution Match
    k_insts = known_institutions.get(author_name, set())
    for k in k_insts:
        if k and len(k) > 1 and k.lower() in inst:
            return True
            
    # 2. Hard Irrelevant Keywords (Filter out obvious namesakes)
    IRRELEVANT_KEYWORDS = [
        '공학', '의학', '간호', '화학', '물리', '생물', '수학', '컴퓨터', '건축', 
        '토목', '전기', '농업', '스포츠', '체육', '부동산', '경영', '마케팅', '회계', '투자', '설계', '소음', '의과',
        'engineering', 'medical', 'nursing', 'chemistry', 'physics', 'biology', 'math', 'computer',
        'architecture', 'civil', 'electric', 'agriculture', 'sports', 'physical', 'real estate', 'business',
        'marketing', 'accounting', 'investment', 'design', 'noise'
    ]
    for kw in IRRELEVANT_KEYWORDS:
        if kw in journal or kw in inst or kw in title:
            return False
            
    # No topic filter anymore! We trust it if it doesn't hit irrelevant keywords.
    return True

def search_kci_author(author_name, known_institutions, max_results=500):
    print(f"  → KCI 검색 (저자: '{author_name}')")
    results = []
    page = 1
    
    while len(results) < max_results:
        url = (
            "https://www.kci.go.kr/kciportal/po/openapi/openApiSearch.kci"
            f"?key={API_KEY}&apiCode=articleSearch"
            f"&author={requests.utils.quote(author_name)}"
            f"&page={page}&displayCount=100"
        )
        try:
            res = requests.get(url, timeout=15)
            if res.status_code != 200:
                break
                
            root = ET.fromstring(res.content)
            records = root.findall(".//record")
            if not records:
                break
                
            for rec in records:
                ji = rec.find("journalInfo")
                ai = rec.find("articleInfo")
                if ai is None: continue
                
                title = _strip_cdata(ai.findtext("title-group/article-title[@lang='original']") or "")
                
                raw_authors = [a.text or "" for a in ai.findall("author-group/author")]
                authors_list, institutions = [], []
                for ra in raw_authors:
                    ra = ra.strip()
                    m = re.match(r"^(.+?)\((.+?)\)$", ra)
                    if m:
                        authors_list.append(m.group(1).strip())
                        institutions.append(m.group(2).strip())
                    elif ra:
                        authors_list.append(ra)
                        institutions.append("")
                        
                j_year = (ji.findtext("pub-year") or "") if ji is not None else ""
                j_name = (ji.findtext("journal-name") or "") if ji is not None else ""
                inst = institutions[0] if institutions else ""
                
                # Must be listed as author
                if author_name not in authors_list:
                    continue
                    
                paper_obj = {
                    'title': title,
                    'authors': ";".join(authors_list),
                    'institution': inst,
                    'year': j_year,
                    'journal': j_name,
                    'type': '학술논문'
                }
                
                if is_relevant(paper_obj, author_name, known_institutions):
                    results.append(paper_obj)
                    
            if len(records) < 100:
                break
            page += 1
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
            
    unique_results.sort(key=lambda x: x['year'], reverse=True)
    return unique_results[:max_results]

def main():
    print("="*50)
    print("Fetching Full Bibliography for Major Researchers (KCI API)")
    print("="*50)
    
    genealogy_researchers = set()
    author_citations = Counter()
    known_institutions = defaultdict(set)
    
    with open(CSV_FILE, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            adv = clean_adv(row.get('지도교수', ''))
            inst = row.get('소속기관', '').strip()
            
            raw_authors = row.get('저자명', '').replace(';', ',').replace('/', ',')
            authors = [clean_adv(a) for a in raw_authors.split(',') if a.strip() and a.strip() != '연구자 없음']
            
            if adv and adv != 'None' and adv != '참고문헌데이터없음':
                genealogy_researchers.add(adv)
                if inst: known_institutions[adv].add(inst)
                for a in authors:
                    if a != adv:
                        genealogy_researchers.add(a)
                        if inst: known_institutions[a].add(inst)
                        
            try: cites = int(row.get('인용된 총 횟수', '0') or 0)
            except ValueError: cites = 0
            
            for a in authors:
                author_citations[a] += cites
                if inst: known_institutions[a].add(inst)
                
    top_authors = [author for author, _ in author_citations.most_common(15) if author]
    for author in top_authors:
        genealogy_researchers.add(author)
    
    major_researchers = [m for m in genealogy_researchers if m and len(m) >= 2]
    print(f"Identified {len(major_researchers)} domestic researchers from genealogy.")
    
    all_data = {}
    if os.path.exists(OUT_JSON):
        with open(OUT_JSON, 'r', encoding='utf-8') as f:
            try:
                all_data = json.load(f)
            except:
                pass
            
    targets = sorted(major_researchers)
    for author in targets:
        print(f"Fetching for: {author}")
        papers = search_kci_author(author, known_institutions, max_results=500)
        all_data[author] = papers
        
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
            
    print(f"Finished. Saved {len(all_data)} authors' bibliographies to {OUT_JSON}.")

if __name__ == "__main__":
    main()
