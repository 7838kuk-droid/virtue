import json
import os

HTML_FILE = "index.html"

def final_polish():
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    marker = "window.__DASHBOARD_DATA__ = "
    start = content.find(marker) + len(marker)
    depth = 0; i = start; in_str = False; esc = False
    while i < len(content):
        c = content[i]
        if esc: esc = False
        elif c == "\\" and in_str: esc = True
        elif c == '"' and not esc: in_str = not in_str
        elif not in_str:
            if c == "[": depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1; break
        i += 1
    
    data = json.loads(content[start:end])
    
    # null 연도 및 초록 매핑 수정
    for p in data:
        # 발행연도 null 방지
        if p.get('발행연도') is None:
            if p.get('발행일자') and '-' in str(p.get('발행일자')):
                try:
                    p['발행연도'] = int(str(p['발행일자']).split('-')[0])
                except:
                    p['발행연도'] = 2026 # Default for new ones if missing
            else:
                p['발행연도'] = 2026
        
        # 초록 필드 동기화 (UI가 국문초록/초록 모두 참조하게 했지만 데이터 자체도 보강)
        if not p.get('국문초록') and p.get('초록'):
            p['국문초록'] = p['초록']
        elif not p.get('초록') and p.get('국문초록'):
            p['초록'] = p['국문초록']

    new_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(content[:start] + new_json + content[end:])
    print("Final polish complete.")

if __name__ == "__main__":
    final_polish()
