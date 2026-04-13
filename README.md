# 덕 윤리 연구 동향 대시보드 (Virtue Ethics Research Dashboard)

국내 KCI 등재지에 등록된 덕 윤리 관련 연구(총 628건)의 지형도와 영향력을 한눈에 파악할 수 있는 Interactive 대시보드입니다.

## 기능 (Features)
- **자동 핵심 키워드 분류**: 논문 제목, 초록, 주제분야 등의 텍스트 기반 정규식 분석을 통해 5대 학제간 카테고리(비교철학, 교육학, 신학, 이론/규범, 응용/실천)로 자동 분석.
- **연도별 연구 동향 차트**: 덕 윤리가 국내 학계에서 어떻게 발전해왔는지 연도별 트렌드를 추적.
- **학제간 융합 카테고리 맵**: 주제분야 비율을 직관적인 ECharts Treemap으로 시각화.
- **버블 매트릭스 영향력 분석**: 연도별 인용 수 현황과 중심 논문 탐색.
- **원클릭 드릴다운(Drill-down)**: 차트 요소 클릭 시 즉시 하단에 해당하는 KCI 원문 바로가기 리스트 생성.

## 기술 스택 (Tech Stack)
- Frontend: HTML, CSS, Vanilla JS
- Build: Vite
- Visualization: Apache ECharts

## 빠른 시작 (Quick Start)
```bash
# 종속성 설치
npm install

# 로컬 개발 서버 실행
npm run dev
```

작업 및 설계는 Anti-Gravity AI에 의해 진행되었습니다.
