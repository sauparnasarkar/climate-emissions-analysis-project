import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, Select, DataTable, Accordion, InlineAlert, Spinner } from 'design-system';
import type { AccordionItem } from 'design-system/components/Accordion/Accordion';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { COUNTRIES } from '../constants';
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

function humanize(field: string): string {
  return field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function ForecastsPage() {
  const [country, setCountry] = useState<string>(COUNTRIES[0]);

  const forecast = useAsync(() => api.forecast(country), [country]);
  const summary = useAsync(() => api.forecastSummary(), []);
  const modelComparison = useAsync(() => api.modelComparison(), []);
  const etsParams = useAsync(() => api.etsParameters(), []);
  const featureImportance = useAsync(() => api.featureImportance(), []);

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
      title: 'ETS(A,Ad,N) Fitted Parameters — All 10 Countries',
      content: (
        <>
          <p className="sy-body4" style={{ marginBottom: 12 }}>
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
        <ChartCard title="RF Pooled Feature Importances — All 10 Countries">
          <SyChart
            height={280}
            orientation="h"
            xTitle="Importance (mean decrease in impurity)"
            yTitle="Feature"
            showLegend={false}
            series={[{ name: 'Importance', x: rows.map((r) => r.feature), y: rows.map((r) => r.importance), kind: 'bar' }]}
          />
        </ChartCard>
      ),
    });
  }

  return (
    <div>
      <h1 className="sy-headline4" style={{ margin: '0 0 8px' }}>ETS(A,Ad,N) Emissions Forecasts (2019–2043)</h1>
      <p className="sy-body3-short" style={{ marginBottom: 16, color: 'var(--sy-static-text-weak)' }}>
        Forecasts from Holt's Damped Trend ETS(A,Ad,N) trained on 1990–2018, with 95% confidence intervals extending to 2043.
      </p>

      <Select label="Select a country" options={COUNTRIES.map((c) => ({ value: c, label: c }))} value={country} onChange={setCountry} />

      <div style={{ margin: '16px 0' }}>
        {forecast.loading ? (
          <Spinner />
        ) : forecast.error ? (
          <InlineAlert variant="warning">{forecast.error}</InlineAlert>
        ) : forecast.data ? (
          <ChartCard title={`ETS(A,Ad,N) Forecast — ${country}`}>
            <SyChart
              height={340}
              xTitle="Year"
              yTitle="CO₂ (MtCO₂)"
              series={[
                { name: 'Historical (1990–2018)', x: forecast.data.hist_years, y: forecast.data.hist_co2, kind: 'line', color: 'steelblue' },
                { name: 'Holdout actuals (2019–2023)', x: forecast.data.holdout_years, y: forecast.data.holdout_co2, kind: 'line', color: 'darkorange' },
                { name: '95% CI', x: forecast.data.forecast_years, y: forecast.data.ci_upper, yLower: forecast.data.ci_lower, kind: 'band', color: '#008000' },
                { name: 'ETS Forecast', x: forecast.data.forecast_years, y: forecast.data.forecast_mean, kind: 'line', color: '#008000' },
              ]}
            />
          </ChartCard>
        ) : null}
      </div>

      <h2 className="sy-headline6">Forecast Summary — All 10 Countries</h2>
      {summary.loading ? (
        <Spinner />
      ) : summary.error ? (
        <InlineAlert variant="warning">{summary.error}</InlineAlert>
      ) : summary.data ? (
        <DataTable columns={SUMMARY_COLUMNS} rows={summary.data.rows} />
      ) : null}

      {accordionItems.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <Accordion multiple items={accordionItems} />
        </div>
      )}
    </div>
  );
}
