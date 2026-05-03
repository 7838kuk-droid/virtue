import re

with open('dashboard_standalone.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Network Chart Container
html_target = '<div class="chart-box full-width" id="bubble-chart-container"></div>'
html_replacement = html_target + '\n      <div class="chart-box full-width" id="network-chart-container" style="height: 700px; margin-top: 20px;"></div>'
content = content.replace(html_target, html_replacement)

# 2. Add initNetworkChart call
init_target = 'initBubbleChart(processedData);'
init_replacement = init_target + '\n    initNetworkChart(processedData);'
content = content.replace(init_target, init_replacement)

# 3. Update Bubble Chart logic
bubble_val_target = "value: [year, item['인용된 총 횟수'] || 0, item['참고문헌 수'] || 1, item['연평균인용지수']],"
bubble_val_replacement = "value: [year, item['인용된 총 횟수'] || 0, item['참고문헌 수'] || 1, item['연평균인용지수'], item.networkImpactScore || 0, item.citedScoreBonus || 0],"
content = content.replace(bubble_val_target, bubble_val_replacement)

bubble_size_target = "return Math.min(Math.max(data[2] * 0.8, 5), 40);"
bubble_size_replacement = "return Math.min(Math.max((data[4] + 1) * 2, 5), 50);"
content = content.replace(bubble_size_target, bubble_size_replacement)

# Tooltip replacement
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

content = content.replace(tooltip_target, tooltip_replacement)

# Update subtext
sub_target = '[지표 안내] X축: 발행연도  |  Y축: 인용수  |  원 크기: 참고문헌 수'
sub_replacement = '[지표 안내] X축: 발행연도  |  Y축: 인용수  |  원 크기: 네트워크 영향력 지수'
content = content.replace(sub_target, sub_replacement)

# 4. Add initNetworkChart function
network_func = """
function initNetworkChart(processedData) {
  const chartDom = document.getElementById('network-chart-container');
  if (!chartDom) return;
  const myChart = echarts.init(chartDom, 'dark');

  const nodes = [];
  const edges = [];
  const colorMap = {
    "비교철학적 접근": "#00b4d8",
    "교육학적 접근": "#ff006e",
    "신학적 접근": "#8338ec",
    "응용/실천 윤리": "#fb5607",
    "이론적/규범적 분석": "#ffbe0b"
  };

  processedData.forEach(paper => {
    if ((paper.cites && paper.cites.length > 0) || (paper.cited_by && paper.cited_by.length > 0)) {
      const cat = paper.categories[0] || "이론적/규범적 분석";
      nodes.push({
        id: paper['논문 ID'],
        name: paper['논문명'],
        value: paper.networkImpactScore || 0,
        symbolSize: Math.min(Math.max((paper.networkImpactScore || 0) + 10, 10), 60),
        itemStyle: { color: colorMap[cat] },
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
    title: { 
      text: '논문 상호 참조 네트워크 (Citation Network)', 
      subtext: '점(Node)은 논문을, 선(Edge)은 인용 관계를 나타냅니다.\\n마우스를 올려 상세 정보를 확인하고 점을 드래그하여 이동할 수 있습니다.',
      left: 'center',
      textStyle: { color: '#e2e8f0', fontWeight: 'bold' }
    },
    tooltip: {
      formatter: function (params) {
        if (params.dataType === 'node') {
          const d = params.data.paperData;
          return `
            <div style="max-width: 300px; white-space: normal;">
              <strong style="color:${params.data.itemStyle.color}">${d['논문명']}</strong><br/>
              - 저자: ${d['저자명']}<br/>
              - 발행연도: ${d['발행연도']}<br/>
              - 영향력 지수: ${d.networkImpactScore}점
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
      roam: true,
      label: { show: false },
      force: { repulsion: 300, edgeLength: [50, 150], gravity: 0.1 },
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
  
  window.addEventListener('resize', () => myChart.resize());
}
"""

content = content.replace('</script>\n</body>', network_func + '\n</script>\n</body>')

with open('dashboard_standalone.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated UI successfully!')
