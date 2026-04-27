# Virtue Ethics Research Dashboard - AI Handover Notes

## 1. Project Overview
- **Objective**: An interactive data visualization dashboard for analyzing KCI (Korea Citation Index) trends in Virtue Ethics research.
- **Current State**: Fully functional standalone HTML file (`dashboard_standalone.html`) containing 628 research papers with embedded metadata and visual analytics using ECharts.

## 2. Key Features
- **Visual Analytics**: Interactive Treemap, Bubble clusters, and secondary filter charts (Applied Ethics sub-categories, Annual Trends).
- **Drill-down Paper List**: Dynamic table showing filtered papers based on dashboard interactions.
- **Detailed Metadata Modal**: Informative pop-up showing abstract, authors, citations, and direct KCI links.
- **Reliable Data Export**:
  - **Excel Copy**: Copies data to the clipboard in a tab-separated format for direct pasting into Excel (bypass local file security blocks).
  - **System Print**: Native Print/PDF generation optimized for academic reporting.

## 3. Technical Constraints & Decisions
### ⚠️ Local File Security (`file:///` protocol)
- **Problem**: When opened as a local file (on macOS/Windows), modern browsers block the generation and download of binary files (Excel, Images, PDFs) via scripts to prevent local file system exploitation.
- **History**: Attempted using libraries like `xlsx`, `html2canvas`, and `html2pdf.js`, but these resulted in corrupted downloads or silent blocks in the user's environment.
- **Solution**: Pivoted to **Clipboard Copy** for Excel and **System Native Print** for PDF. These methods are 100% reliable in restricted local environments.

## 4. Pending Features / Next Steps
- **Hosting**: To enable direct "Download" buttons, the dashboard should be hosted on a web server (e.g., GitHub Pages or Netlify).
- **Data Refresh**: Current data is static. Future integrations could utilize KCI Open API if automated updates are required.
- **Mobile optimization**: Enhancements for smaller screen reading of abstract text.

---
*Created on: 2026-04-22*
