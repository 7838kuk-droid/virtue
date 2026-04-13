import { processData, getTreemapData, getTrendData, getBubbleChartData } from './utils/dataProcessor.js';

let fullData = [];

async function initDashboard() {
  try {
    const response = await fetch('/data.json');
    if (!response.ok) throw new Error('Data fetch failed');
    const rawData = await response.json();
    
    // Process Data
    const { processedData, earliestYear } = processData(rawData);
    fullData = processedData;
    
    const totalPapers = processedData.length;
    const totalCitations = processedData.reduce((sum, item) => sum + (item['인용된 총 횟수'] || 0), 0);
    
    // Update KPI Grid
    document.getElementById('kpi-papers').textContent = totalPapers.toLocaleString() + '건';
    document.getElementById('kpi-citations').textContent = totalCitations.toLocaleString() + '회';
    document.getElementById('kpi-first-year').textContent = earliestYear + '년';
    
    // Initialize Charts
    initTrendChart(processedData);
    initTreemap(processedData);
    initBubbleChart(processedData);
    
  } catch (error) {
    console.error("Error initializing dashboard:", error);
  }
}

// Global Dark Theme Configuration for ECharts
const chartTheme = {
  textStyle: { fontFamily: 'Inter, sans-serif' },
  backgroundColor: 'transparent',
  tooltip: {
    backgroundColor: 'rgba(15, 23, 42, 0.9)',
    borderColor: '#3b82f6',
    textStyle: { color: '#f8fafc' }
  }
};

function initTrendChart(processedData) {
  const chartDom = document.getElementById('trend-chart-container');
  const myChart = echarts.init(chartDom, 'dark');
  const { years, data } = getTrendData(processedData);
  
  const option = {
    ...chartTheme,
    title: { text: '연도별 연구 동향', left: 'center', textStyle: { color: '#e2e8f0', fontWeight: 'bold' } },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: years, axisLine: { lineStyle: { color: '#475569' } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
    series: [{
      data: data,
      type: 'line',
      smooth: true,
      lineStyle: { width: 3, color: '#3b82f6' },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59, 130, 246, 0.5)' },
          { offset: 1, color: 'rgba(59, 130, 246, 0)' }
        ])
      },
      itemStyle: { color: '#3b82f6' }
    }]
  };
  
  myChart.setOption(option);
  
  myChart.on('click', function(params) {
    const year = params.name;
    const filtered = fullData.filter(d => d['발행연도'] == year);
    renderDrillDown(filtered, `선택 연도: ${year}년도 논문`);
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

function initTreemap(processedData) {
  const chartDom = document.getElementById('treemap-container');
  const myChart = echarts.init(chartDom, 'dark');
  const treemapData = getTreemapData(processedData);
  
  const option = {
    ...chartTheme,
    title: { text: '학제간 연구 접근법 (비중)', left: 'center', textStyle: { color: '#e2e8f0', fontWeight: 'bold' } },
    tooltip: { formatter: '{b}: {c}건' },
    series: [{
      type: 'treemap',
      width: '100%', height: '80%',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      itemStyle: {
        borderColor: '#0f172a',
        borderWidth: 2,
        gapWidth: 2
      },
      color: ['#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b'],
      data: treemapData
    }]
  };
  
  myChart.setOption(option);
  
  myChart.on('click', function(params) {
    const category = params.name;
    const filtered = fullData.filter(d => d.category === category);
    renderDrillDown(filtered, `선택 카테고리: ${category} 연구`);
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

function initBubbleChart(processedData) {
  const chartDom = document.getElementById('bubble-chart-container');
  const myChart = echarts.init(chartDom, 'dark');
  const seriesData = getBubbleChartData(processedData);
  
  const option = {
    ...chartTheme,
    title: { 
      text: '영향력 분석 시각화 (Impact Matrix)', 
      subtext: 'X축: 발행연도 | Y축: 인용수 | 크기: 참고문헌 수', 
      left: 'center',
      textStyle: { color: '#e2e8f0', fontWeight: 'bold' }
    },
    legend: { top: 40, textStyle: { color: '#cbd5e1' } },
    tooltip: {
      formatter: function (params) {
        const d = params.data.paperData;
        return `
          <div style="max-width: 300px; white-space: normal;">
            <strong style="color:var(--primary-color)">${d['논문명']}</strong><br/>
            - 저자: ${d['저자명']}<br/>
            - 연도: ${d['발행연도']}<br/>
            - 인용수: ${d['인용된 총 횟수']}회<br/>
            - 연평균 피인용: ${params.data.value[3]}회/년
          </div>
        `;
      }
    },
    xAxis: { 
      type: 'value', 
      scale: true,
      name: '발행연도',
      splitLine: { show: false }, 
      axisLine: { lineStyle: { color: '#475569' } },
      axisLabel: { formatter: '{value}' }
    },
    yAxis: { 
      type: 'value', 
      name: '인용수',
      scale: true,
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
      axisLine: { lineStyle: { color: '#475569' } }
    },
    color: ['#00b4d8', '#ff006e', '#8338ec', '#fb5607', '#ffbe0b'],
    series: seriesData
  };
  
  myChart.setOption(option);
  
  myChart.on('click', function(params) {
    const paperId = params.data.paperData['논문 ID'];
    const filtered = fullData.filter(d => d['논문 ID'] === paperId);
    renderDrillDown(filtered, `선택 논문: ${params.data.paperData['논문명']}`);
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

function renderDrillDown(papers, titleStr) {
  const area = document.getElementById('drill-down-area');
  const title = document.getElementById('drill-down-title');
  const tbody = document.getElementById('paper-table-body');
  
  area.style.display = 'block';
  title.textContent = titleStr + ` (총 ${papers.length}건)`;
  
  tbody.innerHTML = '';
  
  // Sort by citations descending
  papers.sort((a,b) => (b['인용된 총 횟수']||0) - (a['인용된 총 횟수']||0)).forEach(p => {
    const tr = document.createElement('tr');
    
    // KCI Link construction fallback
    const kciLink = p['URL'] || `https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiDetail.kci?artiId=${p['논문 ID']}`;
    
    tr.innerHTML = `
      <td>${p['발행연도']}</td>
      <td style="font-weight: 500;">${p['논문명']}</td>
      <td>${p['저자명']}</td>
      <td><span style="font-size: 0.8rem; background:rgba(255,255,255,0.1); padding: 2px 6px; border-radius:4px;">${p.category || p['주제분야']}</span></td>
      <td style="font-weight: bold; color: var(--primary-color);">${p['인용된 총 횟수'] || 0}</td>
      <td><a href="${kciLink}" target="_blank" class="link-btn">KCI 원문</a></td>
    `;
    tbody.appendChild(tr);
  });
  
  // Smooth scroll
  area.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.addEventListener('DOMContentLoaded', initDashboard);
