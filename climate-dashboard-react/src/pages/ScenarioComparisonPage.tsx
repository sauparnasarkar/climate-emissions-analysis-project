import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, MultiSelect, Radio, DataTable, InlineAlert, Spinner, Icon } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { SCENARIO_COLORS, MAX_SELECTED_COUNTRIES } from '../constants';
import type { ScenarioCumulativeRow } from '../api/types';

const SCENARIO_PANELS = Object.keys(SCENARIO_COLORS);

// Split out so the cumulative/compare fetches only ever start once the expanded country
// list (and its featured-default seed) are already known — avoiding a wasted initial fetch
// for an undefined selection before GET /api/countries resolves.
function ScenarioComparisonContent({ featured, expanded }: { featured: string[]; expanded: string[] }) {
  const [selectedCountries, setSelectedCountries] = useState<string[]>(featured);
  const [treemapScenario, setTreemapScenario] = useState<string>('BAU');
  // Touch-friendly surface for the treemap's hover info (SPEC.md §5.10): a tap never produces
  // a hover on touch devices, so tapping a tile shows the same size + color values here
  // instead -- SyChart cancels Plotly's default drill-to-zoom on tap for this reason.
  const [tappedTileIndex, setTappedTileIndex] = useState<number | null>(null);

  // sort_by only affects the response's own `order` field, which nothing here reads anymore
  // now that the treemap is sized by BAU total (unaffected by the radio) and the table below
  // sorts via its own AG Grid column headers -- fixed at 'BAU' rather than a second control.
  const cumulative = useAsync(() => api.scenarioCumulative('BAU'), []);
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
  // Signed delta: the selected scenario's single 2040 level minus the country's current
  // level -- green (down) means that scenario has this country's emissions falling below
  // today's by 2040, red (up) means still rising. Uses SyChart's own default green/lightgrey/
  // crimson scale (no colorScale override) rather than a one-off scale, the same diverging
  // convention already standardized on Overview's % Change chart.
  const treemapColors = cumulative.data?.rows.map((r) => {
    const level2040 = r.year_2040[treemapScenario];
    const current = r.current_level;
    return level2040 != null && current != null ? level2040 - current : null;
  }) ?? [];

  const panelValues = SCENARIO_PANELS.flatMap(
    (scenario) => (compare.data?.scenarios[scenario] ?? []).flatMap((series) => series.values),
  );
  const yRange: [number, number] = [0, panelValues.length > 0 ? Math.max(...panelValues) : 0];

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Scenario Comparison (2025–2040)</h1>
      <p className="__s9cmpx-body1" style={{ marginBottom: 16, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Compare <strong>Business as Usual (BAU)</strong>, <strong>Moderate Mitigation (−2%/yr)</strong>, and{' '}
        <strong>Aggressive Mitigation (−5%/yr)</strong> starting from 2025.
      </p>

      <h2 className="__s9cmpx-headline6">Reduction Scenarios by Country</h2>
      <p className="__s9cmpx-body2" style={{ marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Tile size is each country&apos;s cumulative BAU emissions, 2025–2040; color is whether the
        selected scenario&apos;s 2040 level is above (red) or below (green) the country&apos;s current level.
      </p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginBottom: 8 }}>
        {SCENARIO_PANELS.map((scenario) => (
          <Radio
            key={scenario}
            name="treemap-scenario"
            label={scenario}
            checked={treemapScenario === scenario}
            onChange={() => setTreemapScenario(scenario)}
          />
        ))}
      </div>
      {cumulative.loading ? (
        <Spinner />
      ) : cumulative.error ? (
        <InlineAlert variant="warning">{cumulative.error}</InlineAlert>
      ) : cumulative.data ? (
        <ChartCard
          title={`Cumulative Emissions & Reduction Scenarios — ${treemapScenario} — ${cumulative.data.rows.length} Expanded Countries`}
          headingLevel={3}
          expandable
        >
          {(isExpanded) => (
            <>
              <SyChart
                height={isExpanded ? 640 : 360}
                showLegend={false}
                ariaLabel={`Treemap of ${cumulative.data!.rows.length} countries, sized by cumulative BAU emissions 2025 to 2040 and colored by whether ${treemapScenario}'s 2040 level is above or below each country's current level`}
                series={[{
                  name: treemapScenario,
                  x: [],
                  y: [],
                  kind: 'treemap',
                  labels: cumulative.data!.rows.map((r) => r.country),
                  parents: cumulative.data!.rows.map(() => ''),
                  values: treemapValues,
                  valueLabel: 'Cumulative BAU',
                  colorValues: treemapColors,
                  colorbarTitle: `${treemapScenario} 2040 vs. Current`,
                  hoverUnit: 'MtCO₂',
                  onTileClick: (pointNumber) => setTappedTileIndex(pointNumber),
                }]}
              />
              {tappedTileIndex != null && cumulative.data!.rows[tappedTileIndex] && (
                <div
                  className="__s9cmpx-body2"
                  style={{
                    marginTop: 8,
                    padding: '10px 12px',
                    borderRadius: 8,
                    background: 'var(--__s9cmpx-static-layer-standard)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                  }}
                >
                  <div>
                    <strong>{cumulative.data!.rows[tappedTileIndex].country}</strong>
                    {' — '}
                    Cumulative BAU: {treemapValues[tappedTileIndex].toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂
                    {', '}
                    {treemapScenario} 2040 vs. Current:{' '}
                    {treemapColors[tappedTileIndex] != null
                      ? `${treemapColors[tappedTileIndex]! >= 0 ? '+' : ''}${treemapColors[tappedTileIndex]!.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                      : '—'}{' '}
                    MtCO₂
                  </div>
                  <button
                    type="button"
                    onClick={() => setTappedTileIndex(null)}
                    aria-label="Dismiss country detail"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--__s9cmpx-static-text-weak)', display: 'flex' }}
                  >
                    <Icon name="close" size={16} />
                  </button>
                </div>
              )}
            </>
          )}
        </ChartCard>
      ) : null}

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">Country Comparison</h2>
        <div className="country-picker-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 16 }}>
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
            {SCENARIO_PANELS.map((scenario) => (
              <ChartCard key={scenario} title={scenario} headingLevel={3} expandable>
                {(isExpanded) => (
                  <SyChart
                    height={isExpanded ? 600 : 300}
                    xTitle="Year"
                    yTitle="CO₂ (MtCO₂)"
                    showLegend={false}
                    yRange={yRange}
                    ariaLabel={`Line chart of ${scenario} CO₂ emissions from 1990 to 2040 for ${selectedCountries.join(', ')}`}
                    series={(compare.data!.scenarios[scenario] ?? []).map((s) => ({
                      name: s.name,
                      x: s.years,
                      y: s.values,
                      kind: 'line' as const,
                    }))}
                  />
                )}
              </ChartCard>
            ))}
          </div>
        ) : null}
      </div>

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">Cumulative Emissions Impact, 2025–2040</h2>
        <p className="__s9cmpx-body4" style={{ marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
          Precise cumulative CO₂ totals per country and scenario — click a column header to sort.
        </p>

        {cumulative.loading ? (
          <Spinner />
        ) : cumulative.error ? (
          <InlineAlert variant="warning">{cumulative.error}</InlineAlert>
        ) : cumulative.data ? (
          <DataTable columns={cumulativeColumns} rows={cumulative.data.rows} />
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
