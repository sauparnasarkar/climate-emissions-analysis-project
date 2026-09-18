import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, MultiSelect, Radio, DataTable, InlineAlert, Spinner, Icon, JumpLinks, useReducedMotion } from 'design-system';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import { MAX_SELECTED_COUNTRIES, SCENARIO_PANELS } from '../constants';
import type { ScenarioCumulativeRow } from '../api/types';

// Countries whose cumulative BAU emissions fall below this share of the total are grouped
// into a single "Other" tile rather than rendered individually -- at the treemap's default
// height the long tail's tiles are too small to hold even a short country name without the
// label overflowing or truncating mid-word (Claude Design theme-adherence review, C7).
// Grouping (rather than suppressing the label on an otherwise-still-tiny unlabeled tile)
// keeps every rendered tile both legible and tap-able. Keyed off BAU value alone, not the
// selected scenario's color, so which countries are grouped stays stable across a scenario
// switch -- only the tiles' colors change.
const OTHER_TREEMAP_SHARE_THRESHOLD = 0.01;

interface TreemapTile {
  label: string;
  value: number;
  color: number | null;
  countryCount: number;
}

// Stable labels (SPEC.md §5.19). "Country Comparison" anchors the shared <h2> above the
// per-scenario ChartCard loop below (one card per SCENARIO_PANELS entry) -- there's no single
// stable per-card target otherwise.
const JUMP_ITEMS: JumpLinkItem[] = [
  { id: 'reduction-map', label: 'Reduction Map', href: '#reduction-map' },
  { id: 'country-comparison', label: 'Country Comparison', href: '#country-comparison' },
  { id: 'cumulative-impact', label: 'Cumulative Impact', href: '#cumulative-impact' },
];

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
  // Signed delta: the selected scenario's single 2040 level minus the country's current level
  // -- negative means that scenario has this country's emissions falling below today's by
  // 2040, positive means still rising. Deliberately no colorScale override here: SyChart's own
  // default is now the theme's published diverging scale (brown/teal, colorblind-safe --
  // Claude Design theme-adherence review, A6/C5), not a one-off. Red/green was ruled out for
  // this exact reason -- it's a CVD failure for an above/below encoding carried by hue alone.
  // Every other colorValues-without-colorScale chart in this app (e.g. Overview's % Change bar
  // chart) shares this same default, so this isn't a one-off departure from an existing red/
  // green convention -- the only chart still genuinely red/green-family is Country Profile's
  // YoY bars, which resolve discrete positive/negative pointColors rather than going through
  // this continuous-scale mechanism at all.
  const treemapColors = cumulative.data?.rows.map((r) => {
    const level2040 = r.year_2040[treemapScenario];
    const current = r.current_level;
    return level2040 != null && current != null ? level2040 - current : null;
  }) ?? [];

  const treemapRows = cumulative.data?.rows ?? [];
  const totalTreemapValue = treemapValues.reduce((sum, v) => sum + v, 0);
  const bigIndices: number[] = [];
  const groupedIndices: number[] = [];
  treemapValues.forEach((v, i) => {
    (totalTreemapValue > 0 && v / totalTreemapValue < OTHER_TREEMAP_SHARE_THRESHOLD ? groupedIndices : bigIndices).push(i);
  });
  const otherTile: TreemapTile | null =
    groupedIndices.length > 0
      ? (() => {
          const value = groupedIndices.reduce((sum, i) => sum + treemapValues[i], 0);
          // Value-weighted average delta, not a plain mean -- otherwise one large outlier
          // among many near-zero small countries gets diluted into an unrepresentative color.
          const withColor = groupedIndices.filter((i) => treemapColors[i] != null);
          const weightSum = withColor.reduce((sum, i) => sum + treemapValues[i], 0);
          const color = weightSum > 0 ? withColor.reduce((sum, i) => sum + treemapColors[i]! * treemapValues[i], 0) / weightSum : null;
          return { label: 'Other', value, color, countryCount: groupedIndices.length };
        })()
      : null;
  const treemapTiles: TreemapTile[] = [
    ...bigIndices.map((i): TreemapTile => ({ label: treemapRows[i].country, value: treemapValues[i], color: treemapColors[i], countryCount: 1 })),
    ...(otherTile ? [otherTile] : []),
  ];

  const panelValues = SCENARIO_PANELS.flatMap(
    (scenario) => (compare.data?.scenarios[scenario] ?? []).flatMap((series) => series.values),
  );
  const yRange: [number, number] = [0, panelValues.length > 0 ? Math.max(...panelValues) : 0];

  const reduceMotion = useReducedMotion();
  // All three jump targets below are always in the DOM as soon as this component mounts (h2s
  // are unconditional, only the chart/table content beneath each is gated).
  useJumpToHashOnLoad(true, reduceMotion);

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Scenario Comparison (2025–2040)</h1>
      <JumpLinks items={JUMP_ITEMS} />
      <p className="__s9cmpx-body1" style={{ marginBottom: 16, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Compare <strong>Business as Usual (BAU)</strong>, <strong>Moderate Mitigation (−2%/yr)</strong>, and{' '}
        <strong>Aggressive Mitigation (−5%/yr)</strong> starting from 2025.
      </p>

      <h2 id="reduction-map" className="__s9cmpx-headline6">Reduction Scenarios by Country</h2>
      <p className="__s9cmpx-body2" style={{ marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Tile size is each country&apos;s cumulative BAU emissions, 2025–2040 (the smallest
        emitters grouped into a single &quot;Other&quot; tile); color (see the colorbar) shows
        whether the selected scenario&apos;s 2040 level is above or below the country&apos;s
        current level.
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
                ariaLabel={`Treemap of ${cumulative.data!.rows.length} countries (the smallest grouped into one "Other" tile), sized by cumulative BAU emissions 2025 to 2040 and colored by whether ${treemapScenario}'s 2040 level is above or below each country's current level`}
                series={[{
                  name: treemapScenario,
                  x: [],
                  y: [],
                  kind: 'treemap',
                  labels: treemapTiles.map((t) => t.label),
                  parents: treemapTiles.map(() => ''),
                  values: treemapTiles.map((t) => t.value),
                  valueLabel: 'Cumulative BAU',
                  colorValues: treemapTiles.map((t) => t.color),
                  colorbarTitle: `${treemapScenario} 2040 vs. Current`,
                  hoverUnit: 'MtCO₂',
                  onTileClick: (pointNumber) => setTappedTileIndex(pointNumber),
                }]}
              />
              {tappedTileIndex != null && treemapTiles[tappedTileIndex] && (
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
                    <strong>
                      {treemapTiles[tappedTileIndex].label}
                      {treemapTiles[tappedTileIndex].countryCount > 1 ? ` (${treemapTiles[tappedTileIndex].countryCount} countries)` : ''}
                    </strong>
                    {' — '}
                    Cumulative BAU: {treemapTiles[tappedTileIndex].value.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂
                    {', '}
                    {treemapScenario} 2040 vs. Current{treemapTiles[tappedTileIndex].countryCount > 1 ? ' (weighted avg.)' : ''}:{' '}
                    {treemapTiles[tappedTileIndex].color != null
                      ? `${treemapTiles[tappedTileIndex].color! >= 0 ? '+' : ''}${treemapTiles[tappedTileIndex].color!.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
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
        {/* id lives here, not on the heading above -- matching Overview's "By Country" fix
            (SPEC.md §5.19/§5.20): the jump target should land on the picker a user actually
            needs to interact with, not just its heading, so the dropdown is guaranteed to be
            the first thing on screen after following the link rather than requiring a further
            manual scroll to reach it. */}
        <div id="country-comparison" className="country-picker-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 16 }}>
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
        <h2 id="cumulative-impact" className="__s9cmpx-headline6">Cumulative Emissions Impact, 2025–2040</h2>
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
