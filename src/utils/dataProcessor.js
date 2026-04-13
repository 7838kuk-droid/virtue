/**
 * dataProcessor.js
 * Processes the raw imported data.json array into categorized metrics for ECharts.
 */

// Basic keyword dictionary for categorizing "Research Approaches"
const categories = [
  {
    name: "비교철학적 접근",
    keywords: ["유학", "맹자", "정약용", "동양", "유교", "주희", "제자백가", "공자", "동서"]
  },
  {
    name: "교육학적 접근",
    keywords: ["교육", "인성", "도덕교육", "학교", "학생", "교사", "함양", "교과"]
  },
  {
    name: "신학적 접근",
    keywords: ["기독교", "신학", "종교", "제자도", "교리문답", "토마스", "아퀴나스", "교회", "성경"]
  },
  {
    name: "응용/실천 윤리",
    keywords: ["스포츠", "의료", "리더십", "공공", "간호", "기업", "경영", "전문직", "생명윤리", "환경", "정보윤리", "체육"]
  },
  {
    name: "이론적/규범적 분석", // Default for others lacking specific context, or theoretical keywords
    keywords: ["정의", "칸트", "의무", "공리주의", "메타윤리", "인식론", "형이상학", "도덕발달", "감정"]
  }
];

function assignCategory(paper) {
  const content = (paper['논문명'] + " " + paper['초록'] + " " + (paper['주제분야'] || "")).toLowerCase();
  
  // Scoring mechanism
  let bestMatch = "이론적/규범적 분석"; // Default fallback
  let maxScore = 0;

  for (let cat of categories) {
    let score = 0;
    for (let word of cat.keywords) {
      if (content.includes(word.toLowerCase())) {
         score++;
      }
    }
    if (score > maxScore) {
      maxScore = score;
      bestMatch = cat.name;
    }
  }
  
  return bestMatch;
}

export function processData(rawData) {
  const currentYear = new Date().getFullYear();
  let earliestYear = 9999;
  
  const processed = rawData.map(item => {
    const pubYear = parseInt(item['발행연도']);
    if (!isNaN(pubYear) && pubYear < earliestYear) earliestYear = pubYear;
    
    const citations = item['인용된 총 횟수'] || 0;
    const yearDiff = Math.max(1, currentYear - (isNaN(pubYear) ? currentYear : pubYear));
    const annualCitationIdx = (citations / yearDiff).toFixed(2);
    
    return {
      ...item,
      category: assignCategory(item),
      연평균인용지수: parseFloat(annualCitationIdx)
    };
  });
  
  return { processedData: processed, earliestYear: earliestYear === 9999 ? 2000 : earliestYear };
}

export function getTreemapData(processedData) {
  const counts = {};
  processedData.forEach(paper => {
    counts[paper.category] = (counts[paper.category] || 0) + 1;
  });
  
  return Object.keys(counts).map(catName => ({
    name: catName,
    value: counts[catName]
  }));
}

export function getBubbleChartData(processedData) {
  // Format for ECharts scatter: [x(Year), y(Citations), size(References), Label]
  // In ECharts, series entries should correspond to categories for proper colored legend.
  
  const seriesData = {};
  
  categories.forEach(c => {
    seriesData[c.name] = [];
  });
  
  processedData.forEach(item => {
    const year = parseInt(item['발행연도']);
    if(isNaN(year)) return;
    
    if (seriesData[item.category]) {
      seriesData[item.category].push({
        name: item['논문명'],
        value: [year, item['인용된 총 횟수'] || 0, item['참고문헌 수'] || 1, item['연평균인용지수']],
        paperData: item
      });
    }
  });

  return Object.keys(seriesData).map(cat => ({
    name: cat,
    data: seriesData[cat],
    type: 'scatter',
    symbolSize: function (data) {
      // Scale bubble by reference count (min 5, max 40 for UI)
      return Math.min(Math.max(data[2] * 0.8, 5), 40);
    },
    emphasis: { focus: 'series' },
    itemStyle: { opacity: 0.8 }
  }));
}

export function getTrendData(processedData) {
  const yearCounts = {};
  processedData.forEach(item => {
    const year = parseInt(item['발행연도']);
    if(!isNaN(year)) {
      yearCounts[year] = (yearCounts[year] || 0) + 1;
    }
  });
  
  const years = Object.keys(yearCounts).map(Number).sort((a,b) => a - b);
  const data = years.map(y => yearCounts[y]);
  
  return { years, data };
}
