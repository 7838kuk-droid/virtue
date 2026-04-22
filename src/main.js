import { processData, getTreemapData, getTrendData, getBubbleChartData, getSubChartData } from './utils/dataProcessor.js';

let fullData = [];

async function initDashboard() {
  try {
    const response = await fetch('/data.json');
    if (!response.ok) throw new Error('Data fetch failed');
    const rawData = await response.json();
    
    window.triggerDrillDownFromTooltip = function(encodedCat, type) {
    const category = decodeURIComponent(encodedCat);
    if (type === 'treemap') {
      const filtered = fullData.filter(d => d.categories.includes(category));
      renderDrillDown(filtered, `선택 카테고리: ${category} 연구 (범주 중복 연구 포함)`, 'treemap');
      updateSubCategoryChart(category);
    } else if (type === 'pie') {
      const filtered = fullData.filter(d => d.categories.includes(currentSelectedCategory) && d.subCategories.includes(category));
      renderDrillDown(filtered, `선택 세부 분야: ${category} (${currentSelectedCategory})`, 'pie');
    }
    const area = document.getElementById('drill-down-area');
    if (area) area.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
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
    initAppliedChart(processedData); // Default initialization
    
    // We can also initialize it with a default category if desired.
    // e.g. initSubChart(processedData, "이론적/규범적 분석");
    
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
    renderDrillDown(filtered, `선택 연도: ${year}년도 논문`, 'trend');
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

function initTreemap(processedData) {
  const chartDom = document.getElementById('treemap-container');
  const myChart = echarts.init(chartDom, 'dark');
  const treemapData = getTreemapData(processedData);
  
  const option = {
    ...chartTheme,
    title: { 
      text: '학제간 연구 접근법 (비중)', 
      subtext: '상자를 클릭하시면 오른쪽에서 세부 분야 별 비중을 볼 수 있어요!\n(상자를 더블 클릭하면 해당 분야의 논문 목록으로 이동합니다)', 
      left: 'center', 
      itemGap: 14,
      textStyle: { color: '#e2e8f0', fontWeight: 'bold' },
      subtextStyle: { color: '#fbbf24', fontSize: 13, backgroundColor: '#1e293b', padding: [10, 16], borderRadius: 8, borderWidth: 1, borderColor: 'rgba(251, 191, 36, 0.4)', fontWeight: 'bold' }
    },
    tooltip: { show: false },
    series: [{
      type: 'treemap',
      width: '95%', height: '75%', top: 80,
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      label: {
        show: true,
        formatter: function(params) {
          const name = params.name.replace(' ', '\n');
          // 'Sense' Layout: Focus on the Name, subtle count below.
          // Balanced using minimal symmetric padding to avoid overflow.
          return `{name|${name}}\n{count|(${params.value}건)}`;
        },
        align: 'center',
        verticalAlign: 'middle',
        position: 'inside',
        rich: {
          name: { 
            color: '#ffffff', 
            fontSize: 18, 
            fontWeight: 'bold', 
            align: 'center', 
            lineHeight: 24,
            textShadowColor: 'rgba(0,0,0,0.5)',
            textShadowBlur: 4,
            textShadowOffsetY: 2
          },
          count: { 
            color: 'rgba(255,255,255,0.8)', 
            fontSize: 13, 
            align: 'center', 
            padding: [4, 0, 0, 0] 
          }
        }
      },
      emphasis: {
        label: {
          show: true,
          formatter: function(params) {
            const name = params.name.replace(' ', '\n');
            return `{name|${name}}\n{count|(${params.value}건)}`;
          },
          rich: {
            name: { color: '#ffffff', fontSize: 19, fontWeight: 'bold', align: 'center', lineHeight: 26 },
            count: { color: '#ffffff', fontSize: 14, align: 'center', padding: [4, 0, 0, 0] }
          }
        }
      },
      itemStyle: {
        borderColor: '#0f172a',
        borderWidth: 2,
        gapWidth: 2
      },
      color: ['#00b4d8', '#ff006e', '#8338ec', '#fb5607', '#ffbe0b'],
      data: treemapData
    }]
  };
  
  myChart.setOption(option);
  
  myChart.on('click', function(params) {
    const category = params.name;
    updateSubCategoryChart(category);
  });

  myChart.on('dblclick', function(params) {
    const category = params.name;
    const filtered = fullData.filter(d => d.categories.includes(category));
    renderDrillDown(filtered, `선택 카테고리: ${category} 연구 (범주 중복 연구 포함)`, 'treemap');
    const area = document.getElementById('drill-down-area');
    if (area) area.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  
  myChart.on('mouseout', function() {
    window._treemapHover = null;
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

let subChartInstance = null;
let currentSelectedCat = "응용/실천 윤리"; // Default choice for retro-compatibility before click

function updateSubCategoryChart(category) {
  initSubChart(fullData, category);
}

function initSubChart(processedData, category) {
  const chartDom = document.getElementById('sub-chart-container');
  if (!chartDom) return;
  if (!subChartInstance) subChartInstance = echarts.init(chartDom, 'dark');
  
  // Set default if not provided
  if(!category) category = "이론적/규범적 분석";
  
  currentSelectedCat = category;
  const chartData = getSubChartData(processedData, category);
  
  const option = {
    ...chartTheme,
    title: { 
      text: `선택된 분야: ${category}`, 
      subtext: '학제별 세부 분야 비중\n(조각을 클릭하면 하단에 원문 리스트가 표시됩니다)', 
      left: 'center', 
      itemGap: 14,
      textStyle: { color: '#60a5fa', fontWeight: 'bold' },
      subtextStyle: { color: '#fbbf24', fontSize: 13, backgroundColor: '#1e293b', padding: [8, 12], borderRadius: 6, borderWidth: 1, borderColor: 'rgba(251, 191, 36, 0.4)', fontWeight: 'bold' }
    },
    tooltip: { show: false },
    legend: { top: 'bottom', textStyle: { color: '#cbd5e1' } },
    series: [
      {
        name: '연구 건수',
        type: 'pie',
        selectedMode: 'single',
        center: ['50%', '50%'],
        radius: ['30%', '50%'],
        itemStyle: {
          borderRadius: 10,
          borderColor: '#0f172a',
          borderWidth: 2
        },
        label: { 
          show: true,
          position: 'outer',
          alignTo: 'labelLine',
          formatter: function(params) {
            let base = `{name|${params.name}}\n{count|${params.value}건}`;
            if (params.data.overlap > 0) {
              base += `\n{percent|(${params.percent}%, 중복 ${params.data.overlap}건)}`;
            } else {
              base += `\n{percent|(${params.percent}%)}`;
            }
            return base;
          }, 
          width: 140,
          overflow: 'break',
          rich: {
            name: { fontSize: 14, fontWeight: 'bold', color: '#e2e8f0', align: 'center', height: 22 },
            count: { fontSize: 14, color: '#f8fafc', fontWeight: 'bold', align: 'center', height: 20 },
            percent: { fontSize: 12, color: '#cbd5e1', align: 'center', height: 18 }
          }
        },
        emphasis: {
          label: { 
             formatter: function(params) {
                let base = `{name|${params.name}}\n{count|${params.value}건}`;
                if (params.data.overlap > 0) {
                  base += `\n{percent|(${params.percent}%, 중복 ${params.data.overlap}건)}`;
                } else {
                  base += `\n{percent|(${params.percent}%)}`;
                }
                return base;
             },
             rich: {
                name: { fontSize: 14, fontWeight: 'bold', color: '#ffffff', align: 'center', height: 22 },
                count: { fontSize: 14, color: '#ffffff', fontWeight: 'bold', align: 'center', height: 20 },
                  fontWeight: 'bold',
                  align: 'center',
                  height: 32
                }
             }
          }
        },
        color: ['#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', 'rgba(255,255,255,0.2)', 'rgba(255,255,255,0.4)'],
        data: chartData
      }
    ]
  };
  
  subChartInstance.setOption(option, true);
  
  subChartInstance.off('click');
  subChartInstance.on('click', function(params) {
    const subCategory = params.name;
    const filtered = fullData.filter(d => d.categories.includes(currentSelectedCat) && d.subCategories.includes(subCategory));
    
    renderDrillDown(filtered, `선택 세부 분야: ${subCategory}`, 'pie');
    const area = document.getElementById('drill-down-area');
    if (area) area.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  
  subChartInstance.on('mouseout', function() {
    window._pieHover = null;
  });
  
  window.addEventListener('resize', () => subChartInstance.resize());
}

function initAppliedChart(processedData) {
  // We repurpose this to initialize the SubChart initially
  initSubChart(processedData, "이론적/규범적 분석");
}

function initBubbleChart(processedData) {
  const chartDom = document.getElementById('bubble-chart-container');
  const myChart = echarts.init(chartDom, 'dark');
  const seriesData = getBubbleChartData(processedData);
  
  const option = {
    ...chartTheme,
    grid: { top: 150, right: 30, bottom: 40, left: 50 },
    title: { 
      text: '영향력 분석 시각화 (Impact Matrix)', 
      subtext: '[지표 안내] X축: 발행연도  |  Y축: 인용수  |  원 크기: 참고문헌 수\n각 원(데이터) 위에 마우스를 올리시면 우측에 상세 정보가 표시됩니다!\n상단 범례의 색상을 클릭하여 특정 분야만 손쉽게 필터링(ON/OFF) 해보세요.', 
      left: 'center',
      itemGap: 14,
      textStyle: { color: '#e2e8f0', fontWeight: 'bold' },
      subtextStyle: { color: '#fbbf24', fontSize: 15, backgroundColor: '#1e293b', padding: [12, 18], borderRadius: 8, borderWidth: 1, borderColor: 'rgba(251, 191, 36, 0.4)', align: 'center', lineHeight: 24, fontWeight: 'bold', shadowColor: 'rgba(0,0,0,0.6)', shadowBlur: 10, shadowOffsetY: 4 }
    },
    legend: { top: 110, itemWidth: 28, itemHeight: 18, textStyle: { color: '#cbd5e1', fontSize: 14, fontWeight: 'bold' } },
    tooltip: {
      formatter: function (params) {
        const d = params.data.paperData;
        return `
          <div style="max-width: 300px; white-space: normal;">
            <strong style="color:var(--primary-color)">${d['논문명']}</strong><br/>
            - 저자: ${d['저자명']}<br/>
            - 연도: ${d['발행연도']}<br/>
            - 참고문헌 수: ${d['참고문헌 수'] || "알 수 없음"}개<br/>
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
      axisLabel: { formatter: function(value) { return String(value); } }
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
    const area = document.getElementById('drill-down-area');
    if (area) area.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  
  window.addEventListener('resize', () => myChart.resize());
}

function renderDrillDown(papers, titleStr, caller = null) {
  const area = document.getElementById('drill-down-area');
  const title = document.getElementById('drill-down-title');
  const tbody = document.getElementById('paper-table-body');
  
  if (!area) return;
  area.style.display = 'block';
  title.textContent = titleStr + ` (총 ${papers.length}건)`;
  
  tbody.innerHTML = '';
  
  // Sort by citations descending
  papers.sort((a,b) => (b['인용된 총 횟수']||0) - (a['인용된 총 횟수']||0)).forEach(p => {
    const tr = document.createElement('tr');
    
    // KCI Link construction fallback
    const kciLink = p['URL'] || `https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=${p['논문 ID']}`;
    
    tr.innerHTML = `
      <td>${p['발행연도']}</td>
      <td style="font-weight: 500;">${p['논문명']}</td>
      <td>${p['저자명']}</td>
      <td style="line-height:1.4;">${
        (p.categories || []).map(c => `<span style="display:inline-block; margin-bottom:4px; font-size: 0.72rem; background:rgba(59,130,246,0.15); border:1px solid rgba(59,130,246,0.3); padding: 2px 6px; border-radius:4px; margin-right:4px;">${c}</span>`).join('')
      }
      <br/>
      ${
        (p.subCategories || []).map(sc => `<span style="display:inline-block; margin-bottom:4px; font-size: 0.72rem; background:rgba(16,185,129,0.15); border:1px solid rgba(16,185,129,0.3); color:#34d399; padding: 2px 6px; border-radius:4px; margin-right:4px;">${sc}</span>`).join('')
      }
      </td>
      <td style="font-weight: bold; color: var(--primary-color);">${p['인용된 총 횟수'] || 0}</td>
      <td style="color: #cbd5e1;">${parseFloat(p['연평균인용지수'] || 0).toFixed(1)}</td>
      <td><button class="link-btn" onclick="showPaperInfo('${encodeURIComponent(JSON.stringify(p)).replace(/'/g, "%27")}')" style="border:none; cursor:pointer; background:rgba(255,255,255,0.15); color:#cbd5e1;">정보 더보기</button></td>
      <td><a href="${kciLink}" target="_blank" class="link-btn">KCI 원문 열람</a></td>
    `;
    tbody.appendChild(tr);
  });
  
  // (We removed the side buttons, so tooltips handle scrolling natively)
}

document.addEventListener('DOMContentLoaded', initDashboard);
