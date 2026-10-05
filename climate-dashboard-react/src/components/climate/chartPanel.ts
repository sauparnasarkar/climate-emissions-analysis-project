// The dark panel Area 2 charts sit on in both themes (design: "Light theme puts charts on a dark chart panel"),
// shared by the landing banner's scatter and the Overview's cumulative-CO₂ view.
export const CHART_PANEL_STYLES = `
.climate-chart-panel { border-radius: 12px; padding: 16px 18px; background: #182746; color: #d7e0f0; display: flex; flex-direction: column; gap: 10px; }
[data-theme="analytics-bright-tidewater"] .climate-chart-panel { background: #061E28; }
`;
