import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, MultiSelect, Radio, DataTable, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { SCENARIO_COLORS, MAX_SELECTED_COUNTRIES } from '../constants';
import type { ScenarioCumulativeRow } from '../api/types';

// Green-only sequential scale for "reduction upside" (more saturated = more upside available)
// -- deliberately distinct from both the Overview % Change chart's green/crimson delta pair
// and the world map's amber/red magnitude scale, since this reads on a different axis
// entirely (potential, not sign or magnitude).
const REDUCTION_UPSIDE_SCALE: Array<[number, string]> = [
  [0, '#eaf7ea'],
  [1, '#1a7a3c'],
];

const SCENARIO_PANELS = Object.keys(SCENARIO_COLORS);

// Split out so the cumulative/compare fetches only ever start once the expanded country
// list (and its featured-default seed) are already known — avoiding a wasted initial fetch
// for an undefined selection before GET /api/countries resolves.
function ScenarioComparisonContent({ featured, expanded }: { featured: string[]; expanded: string[] }) {
  const [selectedCountries, setSelectedCountries] = useState<string[]>(featured);
  const [sortBy, setSortBy] = useState<string>('BAU');

  const cumulative = useAsync(() => api.scenarioCumulative(sortBy), [sortBy]);
  // scenarios/compare has no graceful empty-selection fallback (it requires at least one
  // country) -- short-circuit locally rather than round-tripping to a 422 the same way
  // Overview/Historical Trends's own endpoints tolerate an empty selection.
  const compare = useAsync(
    () => (selectedCountries.length > 0 ? api.scenarioCompare(selectedCountries) : Promise.resolve(null)),
    [selectedCountries.join(',')],
  );

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

  const treemapValues = cumulative.data?.rows.map((r) => r.values.BAU ?? 0) ?? [];
  const treemapColors = cumulative.data?.rows.map((r) => {
    const bau = r.values.BAU;
    const aggressive = r.values.Aggressive;
    return bau ? ((bau - (aggressive ?? bau)) / bau) * 100 : null;
  }) ?? [];

  const panelValues = SCENARIO_PANELS.flatMap(
    (scenario) => (compare.data?.scenarios[scenario] ?? []).flatMap((series) => series.values),
  );
  const yRange: [number, number] = [0, panelValues.length > 0 ? Math.max(...panelValues) : 0];

  return (
    <div data-chart-category="projection">
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Scenario Comparison (2025–2040)</h1>
      <p className="__s9cmpx-body3-short" style={{ marginBottom: 16, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Compare <strong>Business as Usual (BAU)</strong>, <strong>Moderate Mitigation (−2%/yr)</strong>, and{' '}
        <strong>Aggressive Mitigation (−5%/yr)</strong> starting from 2025.
      </p>

      <h2 className="__s9cmpx-headline6">Reduction Upside by Country</h2>
      <p className="__s9cmpx-body4" style={{ marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Tile size is each country&apos;s cumulative BAU emissions, 2025–2040; color is the % reduction
        Aggressive mitigation would achieve versus BAU — darker tiles have more upside available.
      </p>
      {cumulative.loading ? (
        <Spinner />
      ) : cumulative.error ? (
        <InlineAlert variant="warning">{cumulative.error}</InlineAlert>
      ) : cumulative.data ? (
        <ChartCard title={`Cumulative BAU Emissions & Reduction Upside — ${cumulative.data.rows.length} Countries`}>
          <SyChart
            height={360}
            showLegend={false}
            ariaLabel={`Treemap of ${cumulative.data.rows.length} countries, sized by cumulative BAU emissions 2025 to 2040 and colored by percent reduction upside under Aggressive mitigation`}
            series={[{
              name: 'Reduction Upside',
              x: [],
              y: [],
              kind: 'treemap',
              labels: cumulative.data.rows.map((r) => r.country),
              parents: cumulative.data.rows.map(() => ''),
              values: treemapValues,
              colorValues: treemapColors,
              colorScale: REDUCTION_UPSIDE_SCALE,
              colorbarTitle: '% Reduction Upside',
            }]}
          />
        </ChartCard>
      ) : null}

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">Country Comparison</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 16 }}>
          <MultiSelect
            label={`Select countries (up to ${MAX_SELECTED_COUNTRIES}/${expanded.length})`}
            options={expanded.map((c) => ({ value: c, label: c }))}
            value={selectedCountries}
            onChange={setSelectedCountries}
            maxSelected={MAX_SELECTED_COUNTRIES}
          />
        </div>

        {selectedCountries.length === 0 ? (
          <InlineAlert variant="warning">Select at least one country.</InlineAlert>
        ) : compare.loading ? (
          <Spinner />
        ) : compare.error ? (
          <InlineAlert variant="warning">{compare.error}</InlineAlert>
        ) : compare.data ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16 }}>
            {SCENARIO_PANELS.map((scenario, i) => (
              <ChartCard key={scenario} title={scenario}>
                <SyChart
                  height={300}
                  xTitle="Year"
                  yTitle="CO₂ (MtCO₂)"
                  showLegend={i === 0}
                  yRange={yRange}
                  ariaLabel={`Line chart of ${scenario} CO₂ emissions from 1990 to 2040 for ${selectedCountries.join(', ')}`}
                  series={(compare.data!.scenarios[scenario] ?? []).map((s) => ({
                    name: s.name,
                    x: s.years,
                    y: s.values,
                    kind: 'line' as const,
                  }))}
                />
              </ChartCard>
            ))}
          </div>
        ) : null}
      </div>

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">Cumulative Emissions Impact, 2025–2040</h2>
        <p className="__s9cmpx-label2" style={{ marginBottom: 8 }}>Sort by cumulative emissions under scenario</p>
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

export default function ScenarioComparisonPage() {
  const countries = useCountries();

  if (countries.loading) return <Spinner />;
  if (countries.error) return <InlineAlert variant="warning">{countries.error}</InlineAlert>;
  if (!countries.data) return null;

  return <ScenarioComparisonContent featured={countries.data.featured} expanded={countries.data.expanded} />;
}
