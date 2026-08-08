import { useEffect, useRef, useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, Select, DataTable, Accordion, InlineAlert, Spinner, JumpLinks, useReducedMotion } from 'design-system';
import type { AccordionItem } from 'design-system/components/Accordion/Accordion';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import type { EtsParameterRow, ForecastSummaryRow } from '../api/types';

const SUMMARY_COLUMNS: ColDef<ForecastSummaryRow>[] = [
  { field: 'country', headerName: 'Country' },
  { field: 'forecast_2030', headerName: '2030 Forecast (MtCO₂)' },
  { field: 'forecast_2035', headerName: '2035 Forecast' },
  { field: 'forecast_2040', headerName: '2040 Forecast' },
  { field: 'actual_2020', headerName: '2020 Actual' },
  { field: 'pct_change_2020_2040', headerName: '% Change 2020→2040' },
];

const ETS_COLUMNS: ColDef<EtsParameterRow>[] = [
  { field: 'country', headerName: 'Country' },
  { field: 'alpha', headerName: 'α (level)' },
  { field: 'beta_star', headerName: 'β* (trend)' },
  { field: 'phi', headerName: 'φ (damping)' },
];

// Panel DOM id (Accordion's `${id}-accordion-panel` convention) -> accordion item id, for
// resolving a bookmarked hash-jump target to the panel it needs opened first (SPEC.md §5.19).
const PANEL_TO_ACCORDION_ID: Record<string, string> = {
  'model-comparison-accordion-panel': 'model-comparison',
  'ets-params-accordion-panel': 'ets-params',
  'feature-importance-accordion-panel': 'feature-importance',
};

function humanize(field: string): string {
  return field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function countryCount(n: number): string {
  return `${n} ${n === 1 ? 'Country' : 'Countries'}`;
}

// Split out so the forecast fetch only ever starts once the expanded country list (and its
// featured-default seed) are already known — avoiding a wasted initial fetch for an
// undefined country before GET /api/countries resolves.
function ForecastsContent({ expanded, seedCountry }: { expanded: string[]; seedCountry: string }) {
  const [country, setCountry] = useState<string>(seedCountry);
  // Lifted so a jump-nav click can force a specific panel open before scrolling to it (SPEC.md
  // §5.19) -- a closed Accordion panel's content isn't even mounted, so scrolling there without
  // opening it first would land on nothing.
  const [openAccordionIds, setOpenAccordionIds] = useState<string[]>([]);
  const reduceMotion = useReducedMotion();

  const forecast = useAsync(() => api.forecast(country), [country]);
  const summary = useAsync(() => api.forecastSummary('expanded'), []);
  const modelComparison = useAsync(() => api.modelComparison(), []);
  const etsParams = useAsync(() => api.etsParameters(), []);
  const featureImportance = useAsync(() => api.featureImportance(), []);

  // A bookmarked/shared URL might target one of the 3 accordion-backed panels below -- those
  // don't exist in the DOM until their data has loaded AND the panel is open, unlike
  // #forecast-chart/#forecast-summary which are unconditionally in the DOM from first render.
  // Open the targeted panel (once its data is ready) before useJumpToHashOnLoad is allowed to fire.
  const hashAtMount = useRef(window.location.hash.slice(1));
  const targetAccordionId = PANEL_TO_ACCORDION_ID[hashAtMount.current];
  const allAccordionDataReady = Boolean(modelComparison.data && etsParams.data && featureImportance.data);

  useEffect(() => {
    if (targetAccordionId && allAccordionDataReady) {
      setOpenAccordionIds((ids) => (ids.includes(targetAccordionId) ? ids : [...ids, targetAccordionId]));
    }
  }, [targetAccordionId, allAccordionDataReady]);

  const hashJumpReady = targetAccordionId ? allAccordionDataReady && openAccordionIds.includes(targetAccordionId) : true;
  useJumpToHashOnLoad(hashJumpReady, reduceMotion);

  const accordionItems: AccordionItem[] = [];

  if (modelComparison.data) {
    const columns: ColDef[] = modelComparison.data.columns.map((c) => ({ field: c, headerName: humanize(c) }));
    accordionItems.push({
      id: 'model-comparison',
      title: 'Five-Model Comparison Table (MAE / RMSE)',
      content: <DataTable columns={columns} rows={modelComparison.data.rows} />,
    });
  }

  if (etsParams.data) {
    accordionItems.push({
      id: 'ets-params',
      title: `ETS(A,Ad,N) Fitted Parameters — ${countryCount(etsParams.data.rows.length)}`,
      content: (
        <>
          <p className="__s9cmpx-body4" style={{ marginBottom: 12 }}>
            <strong>α</strong> (level smoothing), <strong>β*</strong> (trend smoothing), and <strong>φ</strong> (damping)
            for each country's Holt's Damped Trend model, fit on 1990–2018.
          </p>
          <DataTable columns={ETS_COLUMNS} rows={etsParams.data.rows} />
        </>
      ),
    });
  }

  if (featureImportance.data) {
    const rows = featureImportance.data.rows;
    accordionItems.push({
      id: 'feature-importance',
      title: 'Random Forest Feature Importance (Pooled Model)',
      content: (
        <ChartCard title="RF Pooled Feature Importances — Pooled Model" headingLevel={4}>
          <SyChart
            height={280}
            orientation="h"
            xTitle="Importance (mean decrease in impurity)"
            yTitle="Feature"
            showLegend={false}
            ariaLabel={`Horizontal bar chart ranking ${rows.length} features by importance in the pooled Random Forest model, from ${rows[0]?.feature} (highest) to ${rows[rows.length - 1]?.feature} (lowest)`}
            series={[{ name: 'Importance', x: rows.map((r) => r.feature), y: rows.map((r) => r.importance), kind: 'bar' }]}
          />
        </ChartCard>
      ),
    });
  }

  // Opens an Accordion panel (if not already open) before the jump-nav click scrolls to it --
  // JumpLinks awaits this and then a double-rAF settle before measuring scroll position, so the
  // page doesn't need to know about that timing itself.
  const openPanel = (id: string) => () =>
    setOpenAccordionIds((ids) => (ids.includes(id) ? ids : [...ids, id]));

  // Stable labels (SPEC.md §5.19), distinct from each ChartCard's own (often dynamic) title.
  // The 3 accordion-backed items only appear once their data has actually loaded (matching
  // accordionItems' own conditional construction above) and target the panel's own DOM id
  // (`${id}-accordion-panel`, Accordion's existing convention), not the bare accordion item id.
  const jumpItems: JumpLinkItem[] = [
    { id: 'forecast-chart', label: 'Forecast Chart', href: '#forecast-chart' },
    { id: 'forecast-summary', label: 'Forecast Summary', href: '#forecast-summary' },
    ...(modelComparison.data
      ? [{ id: 'model-comparison-accordion-panel', label: 'Model Comparison', href: '#model-comparison-accordion-panel', onBeforeJump: openPanel('model-comparison') }]
      : []),
    ...(etsParams.data
      ? [{ id: 'ets-params-accordion-panel', label: 'ETS Parameters', href: '#ets-params-accordion-panel', onBeforeJump: openPanel('ets-params') }]
      : []),
    ...(featureImportance.data
      ? [{ id: 'feature-importance-accordion-panel', label: 'Feature Importance', href: '#feature-importance-accordion-panel', onBeforeJump: openPanel('feature-importance') }]
      : []),
  ];

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>ETS(A,Ad,N) Emissions Forecasts (2019–2043)</h1>
      <JumpLinks items={jumpItems} />
      <p className="__s9cmpx-body1" style={{ marginBottom: 16, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Forecasts from Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, with 95% confidence intervals extending to 2043.
      </p>

      <Select label={`Select a country (${expanded.length} available)`} options={expanded.map((c) => ({ value: c, label: c }))} value={country} onChange={setCountry} />

      <div id="forecast-chart" style={{ margin: '16px 0' }}>
        {forecast.loading ? (
          <Spinner />
        ) : forecast.error ? (
          <InlineAlert variant="warning">{forecast.error}</InlineAlert>
        ) : forecast.data ? (
          <ChartCard title={`ETS(A,Ad,N) Forecast — ${country}`} headingLevel={2}>
            <SyChart
              height={340}
              xTitle="Year"
              yTitle="CO₂ (MtCO₂)"
              ariaLabel={`Line chart for ${country}: historical CO₂ emissions 1990 to 2018, holdout actuals 2019 to 2023, and ETS forecast with 95% confidence interval extending to 2043`}
              series={[
                { name: 'Historical (1990–2018)', x: forecast.data.hist_years, y: forecast.data.hist_co2, kind: 'line', color: 'steelblue' },
                { name: 'Holdout actuals (2019–2023)', x: forecast.data.holdout_years, y: forecast.data.holdout_co2, kind: 'line', color: 'darkorange' },
                { name: '95% CI', x: forecast.data.forecast_years, y: forecast.data.ci_upper, yLower: forecast.data.ci_lower, kind: 'band', color: '#008000', fillOpacity: 0.12 },
                { name: 'ETS Forecast', x: forecast.data.forecast_years, y: forecast.data.forecast_mean, kind: 'line', color: '#008000' },
              ]}
            />
          </ChartCard>
        ) : null}
      </div>

      <h2 id="forecast-summary" className="__s9cmpx-headline6">
        {summary.data ? `Forecast Summary — ${countryCount(summary.data.rows.length)}` : 'Forecast Summary'}
      </h2>
      {summary.loading ? (
        <Spinner />
      ) : summary.error ? (
        <InlineAlert variant="warning">{summary.error}</InlineAlert>
      ) : summary.data ? (
        <DataTable columns={SUMMARY_COLUMNS} rows={summary.data.rows} />
      ) : null}

      {accordionItems.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <Accordion multiple items={accordionItems} openIds={openAccordionIds} onOpenChange={setOpenAccordionIds} />
        </div>
      )}
    </div>
  );
}

export default function ForecastsPage() {
  const countries = useCountries();

  if (countries.loading) return <Spinner />;
  if (countries.error) return <InlineAlert variant="warning">{countries.error}</InlineAlert>;
  if (!countries.data) return null;

  return <ForecastsContent expanded={countries.data.expanded} seedCountry={countries.data.featured[0]} />;
}
