export const categoryConfig = {
  "비교철학적 접근": [
    { name: "선진 유학 (공맹)", keywords: ["공자", "맹자", "순자", "선진유학", "제자백가", "논어"] },
    { name: "성리학 및 조선 유학", keywords: ["주희", "퇴계", "율곡", "정약용", "다산", "성리학", "양명학", "조선"] },
    { name: "불교 및 도교 철학", keywords: ["불교", "도교", "장자", "노자", "선불교", "원효"] },
    { name: "동서양 사상 비교", keywords: ["비교연구", "비교철학", "동서양", "서양 철학", "대비"] }
  ],
  "교육학적 접근": [
    { name: "도덕/인성 교육", keywords: ["도덕교육", "인성교육", "인성 교육", "도덕과", "내러티브", "도덕발달", "덕 교육", "교육학"] },
    { name: "교육과정/정책", keywords: ["교육과정", "교과서", "초등", "중등", "학업", "수업", "임용", "교육과"] },
    { name: "교사 윤리", keywords: ["교사", "교직", "예비교사", "교원", "교수"] }
  ],
  "신학적 접근": [
    { name: "기독교/신학 일반", keywords: ["기독교", "신학", "성경", "교회", "그리스도", "종교"] },
    { name: "인물/교리", keywords: ["예수", "바울", "칼빈", "웨슬리", "아퀴나스", "교리", "어거스틴"] },
    { name: "목회/신앙 실천", keywords: ["제자도", "목회", "영성", "신앙", "예배", "성화"] }
  ],
  "이론적/규범적 분석": [
    { name: "고전 덕 윤리", keywords: ["아리스토텔레스", "에우다이모니아", "프로네시스", "아크라시아", "중용", "탁월함"] },
    { name: "현대 덕 윤리", keywords: ["매킨타이어", "허스트하우스", "슬로트", "누스바움", "하우어워스", "안스콤", "현대 덕 윤리"] },
    { name: "규범 이론 비교", keywords: ["칸트", "의무론", "공리주의", "결과주의", "존 롤스", "규범 윤리"] },
    { name: "메타 윤리와 정당화", keywords: ["정당화", "인식론", "형이상학", "도덕적 실재론", "객관성", "메타윤리", "목적론"] },
    { name: "도덕 심리학 및 감정", keywords: ["감정", "공감", "수치심", "부끄러움", "분노", "동정심", "연민", "도덕 심리", "측은지심"] }
  ],
  "응용/실천 윤리": [
    { name: "의료/생명 윤리", keywords: ["간호", "의료", "돌봄", "생명윤리", "임상", "안락사", "연명"] },
    { name: "스포츠/신체 윤리", keywords: ["스포츠", "체육", "도핑", "무도"] },
    { name: "공공/조직 윤리", keywords: ["공직", "조직", "리더십", "경찰", "군인", "경영", "기업", "전문직", "행정", "csr"] },
    { name: "환경과 생태 윤리", keywords: ["환경", "생태", "기후", "동물권"] },
    { name: "공학과 기술 윤리", keywords: ["공학", "인공지능", "로봇", "정보윤리", "ai", "알고리즘", "데이터", "기술", "사이버"] }
  ]
};

const exactFieldMapping = {
  "교육학적 접근": ["교육학", "윤리교육학", "기타교육학", "교과교육학", "초등교육", "컴퓨터교육학", "교육철학/사상", "교육학일반", "경영교육"],
  "신학적 접근": ["기독교신학", "기타기독교신학", "종교학", "한국자생종교", "기타가톨릭신학", "조직신학", "가톨릭신학"],
  "비교철학적 접근": ["유교학", "불교학", "지역불교및불교사연구", "원불교학", "기타유교학", "동양철학일반", "한국철학일반"],
  "응용/실천 윤리": ["체육", "의학일반", "법학", "기타체육", "응용윤리학", "군사이론", "무도학", "신문방송학", "기타사회과학", "기타사회과학일반", "사회과학일반", "국방정책론", "상사법", "특수/장애인체육", "법학일반", "건축공학", "행정학", "행정조직/관리", "한의학", "행정사", "전자/정보통신공학", "사회학", "간호윤리"],
  "이론적/규범적 분석": ["서양철학", "윤리학", "과학/자연철학", "서양고전어와문학", "철학일반", "여성철학", "기타철학일반"]
};

export function processData(rawData) {
  const currentYear = new Date().getFullYear();
  let earliestYear = 9999;
  
  const processed = rawData.map(paper => {
    const pubYear = parseInt(paper['발행연도']);
    if (!isNaN(pubYear) && pubYear < earliestYear) earliestYear = pubYear;
    
    const citations = paper['인용된 총 횟수'] || 0;
    const yearDiff = Math.max(1, currentYear - (isNaN(pubYear) ? currentYear : pubYear));
    const annualCitationIdx = (citations / yearDiff).toFixed(2);
    
    const title = (paper['논문명'] || "").toLowerCase();
    const abstract = (paper['초록'] || "").toLowerCase();
    const field = (paper['주제분야'] || "").trim();
    
    let mainCatSet = new Set();
    let subCatSet = new Set();
    
    // Keyword Matching for Multiple Categories
    for (let mainCat in categoryConfig) {
      categoryConfig[mainCat].forEach(subCat => {
        let matched = false;
        for (let word of subCat.keywords) {
          if (title.includes(word) || abstract.includes(word)) {
            matched = true;
            break;
          }
        }
        if (matched) {
          subCatSet.add(subCat.name);
          mainCatSet.add(mainCat);
        }
      });
    }
    
    // Field Matching via KCI Registration
    for (let mainCat in exactFieldMapping) {
      if (exactFieldMapping[mainCat].includes(field)) {
        mainCatSet.add(mainCat);
      }
    }
    
    if (mainCatSet.size === 0) {
      mainCatSet.add("이론적/규범적 분석");
      subCatSet.add("현대 주요 학자");
    }
    
    const categoriesArray = Array.from(mainCatSet);
    const subCatsArray = Array.from(subCatSet);
    
    return {
      ...paper,
      categories: categoriesArray,
      subCategories: subCatsArray,
      categoryDisplay: categoriesArray.join(", "),
      overlapCount: categoriesArray.length,
      연평균인용지수: parseFloat(annualCitationIdx)
    };
  });
  
  return { processedData: processed, earliestYear: earliestYear === 9999 ? 2000 : earliestYear };
}

export function getTreemapData(processedData) {
  const counts = {};
  processedData.forEach(paper => {
    paper.categories.forEach(cat => {
      counts[cat] = (counts[cat] || 0) + 1;
    });
  });
  
  const orderedCats = ["비교철학적 접근", "교육학적 접근", "신학적 접근", "응용/실천 윤리", "이론적/규범적 분석"];
  const colorMap = {
    "비교철학적 접근": "#00b4d8",
    "교육학적 접근": "#ff006e",
    "신학적 접근": "#8338ec",
    "응용/실천 윤리": "#fb5607",
    "이론적/규범적 분석": "#ffbe0b"
  };
  
  return orderedCats.map(catName => ({
    name: catName,
    value: counts[catName] || 0,
    itemStyle: { color: colorMap[catName] }
  })).filter(cat => cat.value > 0);
}

export function getBubbleChartData(processedData) {
  const seriesData = {};
  
  Object.keys(categoryConfig).forEach(c => {
    seriesData[c] = [];
  });

  processedData.forEach(item => {
    const year = parseInt(item['발행연도']);
    if(isNaN(year)) return;
    
    // Assign to primary category
    const targetCat = item.categories[0];
    
    if (seriesData[targetCat]) {
      seriesData[targetCat].push({
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

export function getSubChartData(processedData, targetMainCat) {
  let subStats = {};

  processedData.forEach(paper => {
    if (paper.categories.includes(targetMainCat)) {
      const mainCatInfo = categoryConfig[targetMainCat];
      if (mainCatInfo) {
        let matchedSubs = [];
        paper.subCategories.forEach(sub => {
          if (mainCatInfo.some(s => s.name === sub)) {
            matchedSubs.push(sub);
          }
        });
        
        matchedSubs.forEach(sub => {
          if(!subStats[sub]) {
            subStats[sub] = { count: 0, overlap: 0 };
          }
          subStats[sub].count++;
          // Overlap strictly defined as matching >1 subcategory within the SAME main category
          if (matchedSubs.length > 1) {
             subStats[sub].overlap++;
          }
        });
      }
    }
  });

  return Object.keys(subStats).map(sub => ({
    name: sub,
    value: subStats[sub].count,
    overlap: subStats[sub].overlap
  }));
}
