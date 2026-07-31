import { Link, Table } from 'design-system';
import { useCountries } from '../hooks/useCountries';

const DATA_SOURCE_ROWS = [
  { dataset: 'OWID CO₂ and GHG Emissions', url: 'https://github.com/owid/co2-data' },
  { dataset: 'Climate Watch Historical Emissions', url: 'https://climatewatchdata.org' },
];

export default function AboutPage() {
  const countries = useCountries();
  // Absolute URL, not relative -- Microsoft's viewer fetches this itself from its own
  // servers, so it needs a URL reachable from the public internet, not just this browser
  // (won't resolve in local dev, since window.location.origin is localhost there; that's expected).
  const presentationUrl = `${window.location.origin}${import.meta.env.BASE_URL}GHG_Internship_Review_QA_Deck.pptx`;

  const methodologyRows = [
    { step: 'Dataset', detail: 'OWID CO₂ dataset, filtered to sovereign nations from 1990 onwards' },
    {
      // Unlike other pages, this renders the table immediately rather than blocking on
      // useCountries() with a top-level Spinner — everything else here is static, so only
      // this one cell should show a brief "Loading…" rather than delaying the whole page.
      step: 'Countries',
      detail: countries.data
        ? `Expanded: ${countries.data.expanded.length} countries (data-quality coverage + emissions-materiality selection). `
          + `Selected (Overview page comparison) defaults to these Featured countries: ${countries.data.featured.join(', ')}.`
        : countries.error
          ? countries.error
          : 'Loading…',
    },
    { step: 'Feature Engineering', detail: 'Lag features (1–3 yrs), 5-yr rolling mean, YoY % change, GHG intensity' },
    { step: 'Train / Test Split', detail: 'Temporal — train 1990–2018, test 2019–2023' },
    { step: 'Models', detail: "Naive Baseline · Linear Regression · Random Forest · ETS(A,Ad,N)" },
    { step: 'Forecasting', detail: "Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, forecast to 2043 with 95% CI" },
    { step: 'Scenarios', detail: 'BAU · Moderate (−2%/yr) · Aggressive (−5%/yr) from 2025' },
  ];

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>About This Project</h1>
      <h2 className="__s9cmpx-headline5" style={{ margin: '16px 0 8px' }}>GHG Emissions Trend Analysis and Forecasting</h2>
      <p className="__s9cmpx-body3-short" style={{ marginBottom: 24 }}>
        This dashboard is a reference implementation for the 7-week data science project conducted as part of the{' '}
        <strong>IDEAS TIH Summer Internship 2026</strong>.
      </p>

      <h3 className="__s9cmpx-headline6" style={{ marginBottom: 8 }}>Methodology Summary</h3>
      <Table
        columns={[
          { key: 'step', header: 'Step' },
          { key: 'detail', header: 'Detail', wrap: true },
        ]}
        rows={methodologyRows}
        withBorder
      />

      <h3 className="__s9cmpx-headline6" style={{ margin: '24px 0 8px' }}>Data Sources</h3>
      <Table
        columns={[
          { key: 'dataset', header: 'Dataset' },
          { key: 'url', header: 'URL', wrap: true, render: (row) => <Link href={row.url} target="_blank" rel="noopener noreferrer">{row.url}</Link> },
        ]}
        rows={DATA_SOURCE_ROWS}
        withBorder
      />

      <h3 className="__s9cmpx-headline6" style={{ margin: '24px 0 8px' }}>Final Presentation</h3>
      <p className="__s9cmpx-body3-short" style={{ marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Internship review Q&amp;A deck, with its original PowerPoint animations and transitions.
        Rendered by Microsoft's own web viewer — if it doesn't load (e.g. before the production
        CSP allows embedding it), use the direct link below instead.
      </p>
      <iframe
        title="GHG Internship Review Q&A Deck"
        src={`https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(presentationUrl)}`}
        style={{ width: '100%', height: 480, border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 4 }}
      />
      <p className="__s9cmpx-body4" style={{ marginTop: 8 }}>
        <Link href={presentationUrl} target="_blank" rel="noopener noreferrer">Open or download the presentation</Link>
      </p>

      <p className="__s9cmpx-body4" style={{ marginTop: 24, color: 'var(--__s9cmpx-static-text-weak)' }}>
        <em>IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar</em>
      </p>
    </div>
  );
}
