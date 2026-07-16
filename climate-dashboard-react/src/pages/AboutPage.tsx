import { Link, Table } from 'design-system';

const METHODOLOGY_ROWS = [
  { step: 'Dataset', detail: 'OWID CO₂ dataset, filtered to sovereign nations from 1990 onwards' },
  { step: 'Countries', detail: 'China, United States, India, Russia, Japan, Germany, Brazil, United Kingdom, South Africa, Australia' },
  { step: 'Feature Engineering', detail: 'Lag features (1–3 yrs), 5-yr rolling mean, YoY % change, GHG intensity' },
  { step: 'Train / Test Split', detail: 'Temporal — train 1990–2018, test 2019–2023' },
  { step: 'Models', detail: "Naive Baseline · Linear Regression · Random Forest · ETS(A,Ad,N)" },
  { step: 'Forecasting', detail: "Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, forecast to 2043 with 95% CI" },
  { step: 'Scenarios', detail: 'BAU · Moderate (−2%/yr) · Aggressive (−5%/yr) from 2025' },
];

const DATA_SOURCE_ROWS = [
  { dataset: 'OWID CO₂ and GHG Emissions', url: 'https://github.com/owid/co2-data' },
  { dataset: 'Climate Watch Historical Emissions', url: 'https://climatewatchdata.org' },
];

export default function AboutPage() {
  return (
    <div>
      <h1 className="sy-headline2" style={{ margin: '0 0 8px' }}>About This Project</h1>
      <h2 className="sy-headline5" style={{ margin: '16px 0 8px' }}>GHG Emissions Trend Analysis and Forecasting</h2>
      <p className="sy-body3-short" style={{ marginBottom: 24 }}>
        This dashboard is a reference implementation for the 7-week data science project conducted as part of the{' '}
        <strong>IDEAS TIH Summer Internship 2026</strong>.
      </p>

      <h3 className="sy-headline6" style={{ marginBottom: 8 }}>Methodology Summary</h3>
      <Table
        columns={[
          { key: 'step', header: 'Step' },
          { key: 'detail', header: 'Detail' },
        ]}
        rows={METHODOLOGY_ROWS}
        withBorder
      />

      <h3 className="sy-headline6" style={{ margin: '24px 0 8px' }}>Data Sources</h3>
      <Table
        columns={[
          { key: 'dataset', header: 'Dataset' },
          { key: 'url', header: 'URL', render: (row) => <Link href={row.url} target="_blank" rel="noreferrer">{row.url}</Link> },
        ]}
        rows={DATA_SOURCE_ROWS}
        withBorder
      />

      <p className="sy-body4" style={{ marginTop: 24, color: 'var(--sy-static-text-weak)' }}>
        <em>IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar</em>
      </p>
    </div>
  );
}
