import os
import json
import re

# 1. We assume git restore has already been run by the bash command before this script.
with open('dashboard_standalone.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# 2. Parse JSON and add Network Impact Score
match = re.search(r'(window\.__DASHBOARD_DATA__\s*=\s*)(\[.*?\])(;)', html_content, re.DOTALL)
if not match:
    print("Error: Could not find JSON data")
    exit(1)

data_str = match.group(2)
data = json.loads(data_str)

for item in data:
    item['clean_title'] = str(item.get('논문명', '')).strip()
    item['cites'] = []
    item['cited_by'] = []
    item['base_cites'] = 0
    try:
        item['base_cites'] = int(item.get('인용된 총 횟수', 0))
    except:
        pass
        
for a in data:
    ref_text = str(a.get('참고문헌목록', '')).replace(' ', '')
    if ref_text and len(ref_text) > 5 and ref_text != 'None' and '참고문헌데이터없음' not in ref_text:
        for b in data:
            if a['논문 ID'] == b['논문 ID']: continue
            t = b['clean_title'].replace(' ', '')
            if len(t) > 5 and t in ref_text:
                a['cites'].append(b['논문 ID'])
                b['cited_by'].append(a['논문 ID'])
                
for a in data:
    cited_score = 0
    for b_id in a['cites']:
        b = next((x for x in data if x['논문 ID'] == b_id), None)
        if b: cited_score += b['base_cites']
    a['networkImpactScore'] = round(a['base_cites'] + (cited_score * 0.2), 1)
    a['citedScoreBonus'] = round(cited_score * 0.2, 1)

for item in data:
    if 'clean_title' in item: del item['clean_title']
    if 'base_cites' in item: del item['base_cites']
    
new_json = json.dumps(data, ensure_ascii=False, indent=2)
html_content = html_content[:match.start(2)] + new_json + html_content[match.end(2):]

# 3. Add Network Chart Container ABOVE Bubble Chart
html_target = '<div class="chart-box full-width" id="bubble-chart-container"></div>'
html_replacement = """      <div class="chart-box full-width" id="network-chart-container" style="height: 750px; position: relative;"></div>
      <div class="chart-box full-width" id="bubble-chart-container" style="margin-top: 20px;"></div>"""
html_content = html_content.replace(html_target, html_replacement)

# 4. Inject initNetworkChart(processedData); call
init_target = 'initBubbleChart(processedData);'
init_replacement = init_target + '\n    initNetworkChart(processedData);'
html_content = html_content.replace(init_target, init_replacement)

# 5. Update Bubble Chart logic
bubble_val_target = "value: [year, item['인용된 총 횟수'] || 0, item['참고문헌 수'] || 1, item['연평균인용지수']],"
bubble_val_replacement = "value: [year, item['인용된 총 횟수'] || 0, item['참고문헌 수'] || 1, item['연평균인용지수'], item.networkImpactScore || 0, item.citedScoreBonus || 0],"
html_content = html_content.replace(bubble_val_target, bubble_val_replacement)

bubble_size_target = "return Math.min(Math.max(data[2] * 0.8, 5), 40);"
bubble_size_replacement = "return Math.min(Math.max((data[4] + 1) * 2, 5), 50);"
html_content = html_content.replace(bubble_size_target, bubble_size_replacement)

tooltip_target = """<strong style="color:var(--primary-color)">${d['논문명']}</strong><br/>
            - 저자: ${d['저자명']}<br/>
            - 연도: ${d['발행연도']}<br/>
            - 참고문헌 수: ${d['참고문헌 수'] || "알 수 없음"}개<br/>
            - 인용수: ${d['인용된 총 횟수']}회<br/>
            - 연평균 피인용: ${params.data.value[3]}회/년"""

tooltip_replacement = """<strong style="color:var(--primary-color)">${d['논문명']}</strong><br/>
            - 저자: ${d['저자명']}<br/>
            - 연도: ${d['발행연도']}<br/>
            - 기본 피인용: ${d['인용된 총 횟수']}회<br/>
            - <strong>네트워크 영향력 지수: ${params.data.value[4]}점</strong><br/>
              <span style="font-size:12px; color:#94a3b8;">(가산점: +${params.data.value[5]}점)</span>"""
html_content = html_content.replace(tooltip_target, tooltip_replacement)

sub_target = '[지표 안내] X축: 발행연도  |  Y축: 인용수  |  원 크기: 참고문헌 수'
sub_replacement = '[지표 안내] X축: 발행연도  |  Y축: 인용수  |  원 크기: 네트워크 영향력 지수'
html_content = html_content.replace(sub_target, sub_replacement)

# 6. Inject initNetworkChart definition
network_func = """
function initNetworkChart(processedData) {
  const chartDom = document.getElementById('network-chart-container');
  if (!chartDom) return;
  const myChart = echarts.init(chartDom, 'dark');

  const controlsDiv = document.createElement('div');
  controlsDiv.style.position = 'absolute';
  controlsDiv.style.top = '20px';
  controlsDiv.style.left = '20px';
  controlsDiv.style.zIndex = '10';
  controlsDiv.style.display = 'flex';
  controlsDiv.style.gap = '10px';
  
  const centerBtn = document.createElement('button');
  centerBtn.innerHTML = '📍 중심부로 가기';
  centerBtn.style.cssText = 'background: rgba(15, 23, 42, 0.8); color: #e2e8f0; border: 1px solid #3b82f6; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-weight: bold; backdrop-filter: blur(4px); box-shadow: 0 4px 6px rgba(0,0,0,0.3);';
  centerBtn.onmouseover = () => centerBtn.style.background = 'rgba(59, 130, 246, 0.3)';
  centerBtn.onmouseout = () => centerBtn.style.background = 'rgba(15, 23, 42, 0.8)';
  centerBtn.onclick = () => {
    myChart.setOption({ series: [{ zoom: 1, center: null }] });
  };
  
  let isZoomLocked = false;
  const lockBtn = document.createElement('button');
  lockBtn.innerHTML = '🔍 확대율 고정해제';
  lockBtn.style.cssText = centerBtn.style.cssText;
  lockBtn.style.borderColor = '#10b981';
  lockBtn.onmouseover = () => lockBtn.style.background = 'rgba(16, 185, 129, 0.3)';
  lockBtn.onmouseout = () => lockBtn.style.background = 'rgba(15, 23, 42, 0.8)';
  lockBtn.onclick = () => {
    isZoomLocked = !isZoomLocked;
    myChart.setOption({ series: [{ roam: !isZoomLocked }] });
    lockBtn.innerHTML = isZoomLocked ? '🔒 확대율 고정됨' : '🔍 확대율 고정해제';
    lockBtn.style.borderColor = isZoomLocked ? '#ef4444' : '#10b981';
  };
  
  controlsDiv.appendChild(centerBtn);
  controlsDiv.appendChild(lockBtn);
  chartDom.appendChild(controlsDiv);

  const nodes = [];
  const edges = [];
  const categories = [
    { name: "비교철학적 접근" },
    { name: "교육학적 접근" },
    { name: "신학적 접근" },
    { name: "응용/실천 윤리" },
    { name: "이론적/규범적 분석" }
  ];
  
  const globalColors = ['#00b4d8', '#ff006e', '#8338ec', '#fb5607', '#ffbe0b'];

  processedData.forEach(paper => {
    if ((paper.cites && paper.cites.length > 0) || (paper.cited_by && paper.cited_by.length > 0)) {
      const cat = paper.categories[0] || "이론적/규범적 분석";
      nodes.push({
        id: paper['논문 ID'],
        name: paper['논문명'],
        category: cat,
        value: paper.networkImpactScore || 0,
        symbolSize: Math.min(Math.max((paper.networkImpactScore || 0) + 10, 10), 60),
        paperData: paper
      });
      
      if (paper.cites) {
        paper.cites.forEach(targetId => {
          edges.push({
            source: paper['논문 ID'],
            target: targetId,
            lineStyle: { color: 'rgba(255,255,255,0.2)', width: 1, curveness: 0.2 }
          });
        });
      }
    }
  });

  const option = {
    backgroundColor: 'transparent',
    color: globalColors,
    title: { 
      text: '논문 상호 참조 네트워크 (Citation Network)', 
      subtext: '점(Node)은 논문을, 선(Edge)은 인용 관계를 나타내며 점의 크기는 [네트워크 영향력 지수]에 비례합니다.\\n마우스를 올려 상세 정보를 확인하고 빈 공간을 드래그하여 화면을 이동할 수 있습니다.',
      left: 'center',
      textStyle: { color: '#e2e8f0', fontWeight: 'bold' }
    },
    legend: {
      data: ["비교철학적 접근", "교육학적 접근", "신학적 접근", "응용/실천 윤리", "이론적/규범적 분석"],
      top: 60,
      textStyle: { color: '#cbd5e1', fontSize: 13, fontWeight: 'bold' }
    },
    tooltip: {
      formatter: function (params) {
        if (params.dataType === 'node') {
          const d = params.data.paperData;
          return `
            <div style="max-width: 300px; white-space: normal;">
              <strong style="color:${params.color}">${d['논문명']}</strong><br/>
              - 저자: ${d['저자명']}<br/>
              - 발행연도: ${d['발행연도']}<br/>
              - <strong>네트워크 영향력 지수: ${d.networkImpactScore}점</strong>
            </div>
          `;
        }
        return '';
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: edges,
      categories: categories,
      roam: true,
      label: { show: false },
      force: { repulsion: 350, edgeLength: [50, 150], gravity: 0.1 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } }
    }]
  };
  
  myChart.setOption(option);
  
  myChart.on('click', function(params) {
    if (params.dataType === 'node') {
        const paperId = params.data.id;
        const filtered = fullData.filter(d => d['논문 ID'] === paperId);
        if (window.renderDrillDown) {
            window.renderDrillDown(filtered, `선택 논문: ${params.data.name}`);
            const area = document.getElementById('drill-down-area');
            if (area) area.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }
  });
  
  window.addEventListener('resize', () => {
    myChart.resize();
  });
}

document.addEventListener"""

html_content = html_content.replace('document.addEventListener', network_func)

with open('dashboard_standalone.html', 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Rebuild Complete!")
