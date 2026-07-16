import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, SegmentedControl, Select, Radio, DataTable, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { COUNTRIES, SCENARIO_COLORS } from '../constants';
import type { ScenarioCumulativeRow } from '../api/types';

type ViewMode = 'single' | 'global';

export default function ScenarioComparisonPage() {
  const [view, setView] = useState<ViewMode>('single');
  const [country, setCountry] = useState<string>(COUNTRIES[0]);
  const [sortBy, setSortBy] = useState<string>('BAU');

  const timeseries = useAsync(
    () => api.scenarioTimeseries(view, view === 'single' ? country : undefined),
    [view, country],
  );
  const cumulative = useAsync(() => api.scenarioCumulative(sortBy), [sortBy]);

  const cumulativeColumns: ColDef<ScenarioCumulativeRow>[] = cumulative.data
    ? [
        { field: 'country', headerName: 'Country' },
        ...cumulative.data.scenarios.map(
          (s): ColDef<ScenarioCumulativeRow> => ({
            colId: s,
            headerName: s,
            valueGetter: (p) => p.data?.values[s],
          }),
        ),
      ]
    : [];

  return (
    <div>
      <h1 className="sy-headline2" style={{ margin: '0 0 8px' }}>Scenario Comparison (2025–2040)</h1>
      <p className="sy-body3-short" style={{ marginBottom: 16, color: 'var(--sy-static-text-weak)' }}>
        Compare <strong>Business as Usual (BAU)</strong>, <strong>Moderate Mitigation (−2%/yr)</strong>, and{' '}
        <strong>Aggressive Mitigation (−5%/yr)</strong> starting from 2025.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
        <SegmentedControl
          items={[
            { value: 'single', label: 'Single Country' },
            { value: 'global', label: 'Global Aggregate' },
          ]}
          value={view}
          onChange={(v) => setView(v as ViewMode)}
        />
        {view === 'single' && (
          <Select label="Select a country" options={COUNTRIES.map((c) => ({ value: c, label: c }))} value={country} onChange={setCountry} />
        )}
      </div>

      {timeseries.loading ? (
        <Spinner />
      ) : timeseries.error ? (
        <InlineAlert variant="warning">{timeseries.error}</InlineAlert>
      ) : timeseries.data ? (
        <ChartCard title={`CO₂ Emissions Scenarios — ${timeseries.data.title_suffix}`}>
          <SyChart
            height={340}
            xTitle="Year"
            yTitle="CO₂ (MtCO₂)"
            referenceY={timeseries.data.level_1990 != null ? { value: timeseries.data.level_1990, label: '1990 level' } : undefined}
            ariaLabel={`Line chart of CO₂ emissions for ${timeseries.data.title_suffix}: historical trend plus BAU, Moderate Mitigation, and Aggressive Mitigation scenarios from 2025 to 2040`}
            series={[
              ...(timeseries.data.historical
                ? [{ name: timeseries.data.historical.name, x: timeseries.data.historical.years, y: timeseries.data.historical.values, kind: 'line' as const, color: 'grey' }]
                : []),
              ...timeseries.data.scenarios.map((s) => ({
                name: s.name,
                x: s.years,
                y: s.values,
                kind: 'line' as const,
                color: SCENARIO_COLORS[s.name],
              })),
            ]}
          />
        </ChartCard>
      ) : null}

      <div style={{ marginTop: 24 }}>
        <h2 className="sy-headline6">Cumulative Emissions Impact, 2025–2040</h2>
        <p className="sy-label2" style={{ marginBottom: 8 }}>Sort by cumulative emissions under scenario</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 16 }}>
          {Object.keys(SCENARIO_COLORS).map((scenario) => (
            <Radio
              key={scenario}
              name="sort-scenario"
              label={scenario}
              checked={sortBy === scenario}
              onChange={() => setSortBy(scenario)}
            />
          ))}
        </div>

        {cumulative.loading ? (
          <Spinner />
        ) : cumulative.error ? (
          <InlineAlert variant="warning">{cumulative.error}</InlineAlert>
        ) : cumulative.data ? (
          <>
            <ChartCard title={`Cumulative CO₂ Emissions by Scenario, 2025–2040 (sorted by ${sortBy})`}>
              <SyChart
                height={340}
                barmode="group"
                xTitle="Country"
                yTitle="Cumulative CO₂, 2025–2040 (MtCO₂)"
                ariaLabel={`Grouped bar chart of cumulative CO₂ emissions from 2025 to 2040 under BAU, Moderate, and Aggressive mitigation scenarios, sorted by ${sortBy}`}
                series={cumulative.data.scenarios.map((scenario) => ({
                  name: scenario,
                  x: cumulative.data!.rows.map((r) => r.country),
                  y: cumulative.data!.rows.map((r) => r.values[scenario] ?? 0),
                  kind: 'bar' as const,
                  color: SCENARIO_COLORS[scenario],
                }))}
              />
            </ChartCard>

            <div style={{ marginTop: 16 }}>
              <DataTable columns={cumulativeColumns} rows={cumulative.data.rows} />
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}
