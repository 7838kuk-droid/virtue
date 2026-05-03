import re

with open('dashboard_standalone.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the network chart function to fix colors and zoom
network_func_match = re.search(r'function initNetworkChart\(processedData\).*?\}\s*document\.addEventListener', content, re.DOTALL)
if network_func_match:
    old_network_func = network_func_match.group(0)
    
    new_network_func = """function initNetworkChart(processedData) {
  const chartDom = document.getElementById('network-chart-container');
  if (!chartDom) return;
  const myChart = echarts.init(chartDom, 'dark');

  // Add Custom Controls for Network Chart
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
    myChart.setOption({
      series: [{ zoom: 1, center: null }]
    });
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
  
  // Ensure the global color palette matches the categories exactly
  const globalColors = ['#00b4d8', '#ff006e', '#8338ec', '#fb5607', '#ffbe0b'];

  processedData.forEach(paper => {
    if ((paper.cites && paper.cites.length > 0) || (paper.cited_by && paper.cited_by.length > 0)) {
      const cat = paper.categories[0] || "이론적/규범적 분석";
      nodes.push({
        id: paper['논문 ID'],
        name: paper['논문명'],
        category: cat, // This binds the node to the legend filtering
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
    
    content = content.replace(old_network_func, new_network_func)

with open('dashboard_standalone.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Updated UI 3 successfully!')
