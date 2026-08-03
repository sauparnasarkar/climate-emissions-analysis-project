import { useMemo, useState, type CSSProperties } from 'react';
import { KpiStat, ChartCard, SyChart, MultiSelect, Button, InlineAlert, Spinner, Icon, Slider } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useCountUp } from '../hooks/useCountUp';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { MAX_SELECTED_COUNTRIES, POSITIVE_COLOR, NEGATIVE_COLOR } from '../constants';
import type { OverviewTierMetrics, WorldMapTimeSeries } from '../api/types';

// How long the KPI numbers take to count up to their new value at each autoplay stop --
// deliberately shorter than ANIMATION_STOP_MS below, leaving the numbers sitting still and
// fully readable for the remainder of the stop rather than still counting (or immediately
// jumping again) right up until the next tick.
const KPI_COUNT_UP_MS = 1200;

// Dwell time at each autoplay stop (useYearAnimation steps by decade, not by year -- year-
// over-year change is gradual enough to be hard to notice, while a decade jump is glaring).
// Set well above KPI_COUNT_UP_MS -- the gap between them (here, ~3s) is how long the settled
// numbers and map color actually stay on screen before the next stop, which is the whole point
// of slowing down: found live that the original pace advanced before the KPI count-up (and the
// reader) had time to register the new figures.
const ANIMATION_STOP_MS = 4200;

// A muted neutral clearly outside MAGNITUDE_SCALE's light-cream-to-deep-red ramp, so a
// no-data country never gets mistaken for a real (if low) value.
const NO_DATA_COLOR = '#4a4a4a';

// Sequential light -> amber -> deep-red magnitude scale for the world map, distinct from
// both the % Change chart's green/crimson delta pair and Scenario Comparison's green-only
// reduction-upside scale -- three visually distinct conventions, each used for one concept.
const MAGNITUDE_SCALE: Array<[number, string]> = [
  [0, '#fff2cc'],
  [0.5, '#f0a24a'],
  [1, '#7a1f1f'],
];

// Standard clip-based visually-hidden technique -- design-system has no existing utility
// class for this, and it's only needed in this one place.
const VISUALLY_HIDDEN: CSSProperties = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: 0,
};

// A component (not a bare hook call) so each instance gets its own independent animation --
// used anywhere a KPI number should count up rather than jump straight to its new value.
// The animating text is aria-hidden (a screen reader shouldn't announce a meaningless
// mid-flight number, or on a 1.5s animation, potentially read a stale one) with the final
// value exposed via an adjacent visually-hidden span instead (SPEC.md §5.10).
function CountUpText({ value, format, durationMs }: { value: number; format: (n: number) => string; durationMs?: number }) {
  const animated = useCountUp(value, durationMs);
  return (
    <>
      <span aria-hidden="true">{format(animated)}</span>
      <span style={VISUALLY_HIDDEN}>{format(value)}</span>
    </>
  );
}

// One glyph per tier so the three cards are visually distinguishable at a glance, not just by
// their text label: grid (every country), document (a defined/documented criteria-based subset),
// check (an explicit user selection). All three already exist in design-system's Icon set.
type TierIcon = 'grid' | 'document' | 'check';

interface TierRow {
  tier: string;
  icon: TierIcon;
  countries: number;
  co2Total: number;
  pctChange: number;
  // True only at the animation's first frame (the map's minYear itself) -- "% Change since
  // {minYear}" is trivially +0.0% there, which reads as broken rather than informative.
  suppressPctChange?: boolean;
}

// Builds a TierRow from a per-year series and the currently-playing frame, rather than
// reading OverviewResponse's static (always-latest-year) figures. countriesCount stays a
// plain number -- it doesn't vary by year.
function animatedTierRow(
  title: string,
  icon: TierIcon,
  countriesCount: number,
  co2ByYear: number[],
  yearIdx: number,
): TierRow {
  const co2Total = co2ByYear[yearIdx] ?? 0;
  const base = co2ByYear[0] ?? 0;
  const pctChange = base ? ((co2Total - base) / base) * 100 : 0;
  return { tier: title, icon, countries: countriesCount, co2Total, pctChange, suppressPctChange: yearIdx === 0 };
}

// Three stacked mini cards (one per tier) instead of a 4-column table — reads better at
// ~33% width than a table whose columns would otherwise be squeezed illegibly narrow.
// Each card shows the same three metrics vertically; the wrapper class carries this
// component's one-off responsive/layout CSS the same way overview-tier-table (its
// table-based predecessor) scoped its own header-background rule.
function TierSummaryPanel({ rows, year, durationMs }: { rows: TierRow[]; year: number; durationMs?: number }) {
  return (
    <div className="overview-tier-panel">
      <style>{`
        .overview-tier-panel { display: flex; flex-direction: column; gap: 12px; }
        .overview-tier-panel__card { padding: 12px 16px; border: 1px solid var(--__s9cmpx-static-divider-weak); border-radius: 8px; flex: 1; }
        .overview-tier-panel__metric { display: flex; justify-content: space-between; padding: 4px 0; }
        .overview-tier-panel__metric + .overview-tier-panel__metric { border-top: 1px solid var(--__s9cmpx-static-divider-weak); }
      `}</style>
      {rows.map((row) => (
        <div key={row.tier} className="overview-tier-panel__card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span className="__s9cmpx-headline5" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{row.tier}</span>
            <Icon name={row.icon} size={20} style={{ color: 'var(--__s9cmpx-interactive-fill-link-default, #1c5ece)' }} />
          </div>
          <div className="overview-tier-panel__metric">
            <span className="__s9cmpx-body2">Countries</span>
            <span className="__s9cmpx-headline4"><CountUpText value={row.countries} format={(n) => Math.round(n).toLocaleString()} durationMs={durationMs} /></span>
          </div>
          <div className="overview-tier-panel__metric">
            <span className="__s9cmpx-body2">{`CO₂ (${year})`}</span>
            <span className="__s9cmpx-headline4"><CountUpText value={row.co2Total} format={(n) => `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`} durationMs={durationMs} /></span>
          </div>
          <div className="overview-tier-panel__metric">
            <span className="__s9cmpx-body2">% Change since 1990</span>
            <span className="__s9cmpx-headline4" style={{ color: row.pctChange >= 0 ? NEGATIVE_COLOR : POSITIVE_COLOR }}>
              {row.suppressPctChange ? (
                '—'
              ) : (
                <CountUpText value={row.pctChange} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} durationMs={durationMs} />
              )}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

// Only ever mounted once worldMapSeries has actually loaded (see OverviewContent's gate) --
// so useYearAnimation below always receives its real min/max year from this component's very
// first render, never a placeholder that would need to change after mount.
function AnimatedWorldMap({
  worldMapSeries,
  selected,
  allCountriesTier,
  expandedTier,
}: {
  worldMapSeries: WorldMapTimeSeries;
  selected: string[];
  allCountriesTier: OverviewTierMetrics;
  expandedTier: OverviewTierMetrics;
}) {
  const minYear = worldMapSeries.years[0];
  const maxYear = worldMapSeries.years[worldMapSeries.years.length - 1];
  const { currentYear, isPlaying, toggle, seek, reducedMotion } = useYearAnimation({
    minYear,
    maxYear,
    intervalMs: ANIMATION_STOP_MS,
  });
  const yearIdx = currentYear - minYear;

  // Memoized to worldMapSeries alone (fetched once, stable for the page's lifetime) -- must
  // never change reference as currentYear advances, or SyChart's main effect re-runs on every
  // tick and undoes the whole point of the animationFrame escape hatch (loses the user's map
  // zoom, rebinds hover handlers, tears down/recreates the resize ResizeObserver).
  const series = useMemo(
    () => [
      {
        name: 'CO₂',
        x: [],
        y: [],
        kind: 'choropleth' as const,
        locations: worldMapSeries.iso_codes,
        zLog: true,
        colorValues: worldMapSeries.values[0],
        colorRange: worldMapSeries.value_range,
        noDataColor: NO_DATA_COLOR,
        colorScale: MAGNITUDE_SCALE,
        colorbarTitle: 'CO₂ (MtCO₂)',
        hoverUnit: 'MtCO₂',
      },
    ],
    [worldMapSeries],
  );

  // Selected's per-year total isn't server-provided (co2_by_year is only populated for All
  // Countries/Expanded) -- summed here from the same columnar series the map already holds,
  // restricted to whichever countries are currently selected. Recomputed only when the series
  // or the selection changes, not per animation tick.
  const selectedIndices = useMemo(() => {
    const selectedNames = new Set(selected);
    const indices: number[] = [];
    worldMapSeries.countries.forEach((country, idx) => {
      if (selectedNames.has(country)) indices.push(idx);
    });
    return indices;
  }, [worldMapSeries, selected]);
  const selectedCo2ByYear = useMemo(
    () => worldMapSeries.values.map((row) => selectedIndices.reduce((sum, idx) => sum + (row[idx] ?? 0), 0)),
    [worldMapSeries, selectedIndices],
  );

  return (
    <>
      <ChartCard title={`CO₂ Emissions by Country (${currentYear})`} headingLevel={2} expandable>
        <div style={{ marginBottom: 8, display: 'flex', gap: 12, alignItems: 'center' }}>
          <Button variant="ghost-blue" onClick={toggle} disabled={reducedMotion}>
            {isPlaying ? 'Pause' : 'Play'}
          </Button>
          <div style={{ flex: 1 }}>
            <Slider label="Year" min={minYear} max={maxYear} step={1} value={currentYear} onChange={seek} showValue />
          </div>
        </div>
        {/* No explicit height here, expanded or not -- the choropleth's own ResizeObserver
            already recomputes height from container width alone (SPEC.md §5.10), so widening
            the container on expand is sufficient. Coexists with SyChart's own internal
            "Reset view" control (a different button, in a different location). */}
        <SyChart
          showLegend={false}
          ariaLabel={`Animated world map choropleth of CO₂ emissions by country, ${minYear} to ${maxYear}, currently showing ${currentYear}, log-scaled color from light (lowest) to deep red (highest)`}
          series={series}
          animationFrame={{ colorValues: worldMapSeries.values[yearIdx] }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
          <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: NO_DATA_COLOR, display: 'inline-block' }} />
          <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
            Gray = no CO₂ data reported for that country in {currentYear}
          </span>
        </div>
      </ChartCard>

      <TierSummaryPanel
        year={currentYear}
        durationMs={KPI_COUNT_UP_MS}
        rows={[
          animatedTierRow('All Countries', 'grid', allCountriesTier.countries_count, allCountriesTier.co2_by_year, yearIdx),
          animatedTierRow('Expanded (Coverage + ≥100 Mt)', 'document', expandedTier.countries_count, expandedTier.co2_by_year, yearIdx),
          ...(selected.length > 0
            ? [animatedTierRow('Selected', 'check', selected.length, selectedCo2ByYear, yearIdx)]
            : []),
        ]}
      />
    </>
  );
}

// Split out so the overview fetch only ever starts once the expanded country list (and its
// featured-default seed) are already known — avoiding a wasted initial fetch before
// GET /api/countries resolves.
function OverviewContent({ featured, expanded }: { featured: string[]; expanded: string[] }) {
  const [selected, setSelected] = useState<string[]>(featured);
  // Still fires even when selected is empty (client.ts omits the query param, server
  // defaults to FEATURED_COUNTRIES) — matches HistoricalTrendsPage's exact precedent. The
  // Selected tier/charts/movers below are gated on the *local* selected.length, not on
  // whatever the server happened to default to, so an empty selection reliably shows the
  // warning regardless of what data resolves to.
  const { data, error, loading } = useAsync(() => api.overview(selected), [selected.join(',')]);
  // Selection-invariant -- deps: [] means this fires exactly once for the page's lifetime,
  // regardless of how many times `selected` changes (SPEC.md §5.17.1).
  const { data: worldMapSeries, error: worldMapError, loading: worldMapLoading } = useAsync(() => api.worldMapSeries(), []);

  // useAsync preserves the previous `data` while a refetch is in flight (only `loading`
  // flips), so only block on a spinner before anything has ever loaded — once `data`
  // exists, keep the picker/last-good UI mounted across every selection change instead of
  // unmounting the whole page (and its MultiSelect) on every refetch.
  if (error || worldMapError) return <InlineAlert variant="warning">{error ?? worldMapError}</InlineAlert>;
  if (!data || !worldMapSeries) return loading || worldMapLoading ? <Spinner /> : null;

  const barSeries = data.latest_year_bar.map((c) => c.country);
  const barValues = data.latest_year_bar.map((c) => c.value ?? 0);

  const moverCountries = data.top_movers.map((m) => m.country);
  const moverPct = data.top_movers.map((m) => m.pct_change ?? 0);

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: 0 }}>GHG Emissions Trend Analysis and Forecasting</h1>
      <p className="__s9cmpx-body1" style={{ margin: '4px 0 16px', color: 'var(--__s9cmpx-static-text-weak)' }}>
        An end-to-end analysis of greenhouse gas emissions for {data.expanded_countries.countries_count} major countries using the OWID CO₂ dataset,
        regression models, and ETS(A,Ad,N) forecasting.
      </p>

      {/* 1400px, not the original 900px -- covers both reported iPad orientations (portrait
          1024, landscape 1366): at either width, the 2fr column left the choropleth too
          narrow for a world map, forced tall by the taller TierSummaryPanel sharing its row
          (SPEC.md §5.10). */}
      <style>{'@media (max-width: 1400px) { .overview-hero-grid { grid-template-columns: 1fr !important; } }'}</style>
      <div className="overview-hero-grid" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 16, alignItems: 'stretch' }}>
        <AnimatedWorldMap
          worldMapSeries={worldMapSeries}
          selected={selected}
          allCountriesTier={data.all_countries}
          expandedTier={data.expanded_countries}
        />
      </div>

      <div className="country-picker-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 12 }}>
        <MultiSelect
          label={`Select countries (up to ${MAX_SELECTED_COUNTRIES}/${expanded.length})`}
          options={expanded.map((c) => ({ value: c, label: c }))}
          value={selected}
          onChange={setSelected}
          maxSelected={MAX_SELECTED_COUNTRIES}
        />
        <Button variant="ghost-blue" onClick={() => setSelected(featured)}>Reset to default</Button>
      </div>

      {selected.length === 0 ? (
        <InlineAlert variant="warning">Select at least one country.</InlineAlert>
      ) : (
        <>
          <ChartCard title={`CO₂ Emissions by Country (${data.selected.latest_year})`} headingLevel={2}>
            <SyChart
              height={320}
              xTitle="Country"
              yTitle="CO₂ (MtCO₂)"
              showLegend={false}
              ariaLabel={`Bar chart of total CO₂ emissions in ${data.selected.latest_year} for ${barSeries.length} countries, ranging from ${Math.min(...barValues).toLocaleString()} to ${Math.max(...barValues).toLocaleString()} MtCO₂`}
              // Explicit brand color -- a single-series bar chart would otherwise default to
              // the categorical palette's index-0 token, which Release 7 (SPEC.md §5.12)
              // deliberately made near-white for multi-line chart hierarchies. That reads as a
              // washed-out, colorless bar rather than a real color, so this chart gets the
              // app's own brand blue instead.
              series={[{ name: 'CO₂', x: barSeries, y: barValues, kind: 'bar', color: 'var(--__s9cmpx-color-brand-500)' }]}
            />
          </ChartCard>

          <div style={{ marginTop: 24 }}>
            <h2 className="__s9cmpx-headline6">Top Movers Since 1990 ({data.selected_country_list.length} Selected Countries)</h2>
            <p className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
              Fastest growth and largest reduction in CO₂ emissions, 1990 → {data.selected.latest_year}, among the {data.selected_country_list.length} selected countries.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, margin: '12px 0 16px' }}>
              <KpiStat
                card
                label={`Fastest Growth — ${data.fastest_growth.country}`}
                value={<CountUpText value={data.fastest_growth.pct_change ?? 0} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} />}
                delta={`${(data.fastest_growth.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.fastest_growth.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="bad"
              />
              <KpiStat
                card
                label={`Largest Reduction — ${data.largest_reduction.country}`}
                value={<CountUpText value={data.largest_reduction.pct_change ?? 0} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} />}
                delta={`${(data.largest_reduction.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.largest_reduction.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="good"
              />
            </div>

            <ChartCard title={`CO₂ % Change by Country, 1990–${data.selected.latest_year}`} headingLevel={3}>
              <SyChart
                height={320}
                xTitle="Country"
                yTitle={`% Change in CO₂ (1990→${data.selected.latest_year})`}
                showLegend={false}
                ariaLabel={`Bar chart of percent change in CO₂ emissions from 1990 to ${data.selected.latest_year} for ${moverCountries.length} countries, colored on a gradient from green (decrease) to crimson (increase)`}
                series={[{
                  name: '% Change',
                  x: moverCountries,
                  y: moverPct,
                  kind: 'bar',
                  colorValues: moverPct,
                  colorbarTitle: `% Change in CO₂ (1990→${data.selected.latest_year})`,
                }]}
              />
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}

export default function OverviewPage() {
  const countries = useCountries();

  if (countries.loading) return <Spinner />;
  if (countries.error) return <InlineAlert variant="warning">{countries.error}</InlineAlert>;
  if (!countries.data) return null;

  return <OverviewContent featured={countries.data.featured} expanded={countries.data.expanded} />;
}
