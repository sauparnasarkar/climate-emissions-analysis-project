import { useMemo, useState, type CSSProperties } from 'react';
import { KpiStat, ChartCard, SyChart, MultiSelect, Button, InlineAlert, Spinner, Slider } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useCountUp } from '../hooks/useCountUp';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { buildHeadlineSentence } from '../lib/overviewHeadline';
import { MAX_SELECTED_COUNTRIES, POSITIVE_COLOR, NEGATIVE_COLOR } from '../constants';
import type { MoverRow, OverviewTierMetrics, WorldMapTimeSeries } from '../api/types';

// Dwell time at each autoplay stop (useYearAnimation steps every 5 years, not by year -- year-
// over-year change is gradual enough to be hard to notice, while a multi-year jump is glaring).
// The KPI tier numbers snap directly to their new value each stop rather than counting up --
// no separate animation duration to coordinate with this one.
const ANIMATION_STOP_MS = 1200;

// A muted neutral clearly outside MAGNITUDE_SCALE's pale-yellow-to-deep-maroon ramp, so a
// no-data country never gets mistaken for a real (if low) value.
const NO_DATA_COLOR = '#4a4a4a';

// Sequential pale-yellow -> orange -> deep-maroon magnitude scale for the world map, distinct
// from both the % Change chart's green/crimson delta pair and Scenario Comparison's green-only
// reduction-upside scale -- three visually distinct conventions, each used for one concept.
// 9 stops (ColorBrewer's YlOrRd), not 3 -- colorRange is pinned across the whole 1990-2024
// animation (SPEC.md §5.17.2) and most countries, most years, sit in the same middle band of
// that fixed range, where a coarse 3-stop scale interpolates almost linearly and reads as
// near-identical shades of orange. More stops means more perceptually distinct color at the
// values that actually vary year to year, making the 1990-vs-2024 difference easier to read at
// a glance without touching colorRange itself (which must stay the true global min/max, per
// §5.17.2 -- narrowing or padding it would re-introduce the per-frame-renormalization problem
// that prop exists to prevent).
const MAGNITUDE_SCALE: Array<[number, string]> = [
  [0, '#ffffcc'],
  [0.125, '#ffeda0'],
  [0.25, '#fed976'],
  [0.375, '#feb24c'],
  [0.5, '#fd8d3c'],
  [0.625, '#fc4e2a'],
  [0.75, '#e31a1c'],
  [0.875, '#bd0026'],
  [1, '#800026'],
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

interface TierRow {
  tier: string;
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
  countriesCount: number,
  co2ByYear: number[],
  yearIdx: number,
): TierRow {
  const co2Total = co2ByYear[yearIdx] ?? 0;
  const base = co2ByYear[0] ?? 0;
  const pctChange = base ? ((co2Total - base) / base) * 100 : 0;
  return { tier: title, countries: countriesCount, co2Total, pctChange, suppressPctChange: yearIdx === 0 };
}

// Each tier gets a full-width heading line (its name, e.g. "Expanded (Coverage + ≥100 Mt)") above
// a compact 3-column metric strip, rather than a single 4-column table (SPEC.md §5.18.2 original
// shape). A shared 4-column table crammed the tier name into ~130px of a ~380-450px-wide panel --
// measured directly against the DOM: "Expanded (Coverage + ≥100 Mt)" needs 204px and was getting
// 133px, truncating to "Expanded (Cover..." and losing the coverage/materiality qualifier this
// tier's whole definition rests on. Promoting the name to its own full-width line gives it the
// panel's entire width to wrap into instead, while Countries/CO₂/%Change -- short, fixed-format
// numbers that were never the truncation risk -- stay in a compact strip below it. Still one
// visually compact block (a shared border, no per-tier cards/icons), not the taller card layout
// this replaced.
// No count-up animation here -- these three metrics change every autoplay tick (as often as
// every 1.2s), so they snap directly to the new value in step with the map rather than easing,
// which would otherwise either lag behind the map or still be mid-animation when the next tick
// arrives. CountUpText (below) stays reserved for values that only ever change once, on load.
function TierSummaryPanel({ rows, year }: { rows: TierRow[]; year: number }) {
  return (
    <div style={{ border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, overflow: 'hidden' }}>
      {rows.map((row, i) => (
        <div
          key={row.tier}
          style={{ padding: '8px 12px', borderTop: i === 0 ? undefined : '1px solid var(--__s9cmpx-static-divider-weak)' }}
        >
          <div className="__s9cmpx-label3" style={{ marginBottom: 6 }}>{row.tier}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
            <div>
              <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Countries</div>
              <div className="__s9cmpx-body2">{Math.round(row.countries).toLocaleString()}</div>
            </div>
            <div>
              <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{`CO₂ (${year})`}</div>
              <div className="__s9cmpx-body2">{`${row.co2Total.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}</div>
            </div>
            <div>
              <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>% Chg. since 1990</div>
              <div className="__s9cmpx-body2" style={{ color: row.pctChange >= 0 ? NEGATIVE_COLOR : POSITIVE_COLOR }}>
                {row.suppressPctChange ? '—' : `${row.pctChange >= 0 ? '+' : ''}${row.pctChange.toFixed(1)}%`}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// The Overview headline sentence (SPEC.md §5.18.1, decoupled from the picker in §5.18.5) -- a
// deterministic, data-derived one-sentence summary of who's grown/declined the most since 1990
// among a fixed top-emitters set, placed above the compressed tier table in the hero row's right
// column. Renders nothing when there's not enough usable data (see buildHeadlineSentence's own
// null cases).
function OverviewHeadline({ headlineMovers, scope }: { headlineMovers: MoverRow[]; scope: string }) {
  const sentence = buildHeadlineSentence(headlineMovers, scope);
  if (!sentence) return null;
  return (
    <div style={{ padding: '12px 16px', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8 }}>
      <span className="__s9cmpx-label3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Since 1990</span>
      <p className="__s9cmpx-body2" style={{ margin: '4px 0 0' }}>{sentence}</p>
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
  headlineMovers,
}: {
  worldMapSeries: WorldMapTimeSeries;
  selected: string[];
  allCountriesTier: OverviewTierMetrics;
  expandedTier: OverviewTierMetrics;
  headlineMovers: MoverRow[];
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
            <Slider
              label="Year"
              min={minYear}
              max={maxYear}
              step={1}
              value={currentYear}
              onChange={seek}
              showValue={false}
              showRangeLabels
              showThumbValue
            />
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

      <div className="overview-hero-right" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* Selection-invariant (SPEC.md §5.18.5) -- headlineMovers is a fixed top-N set from the
            server, independent of the picker, so this stays visible even at 0 selected
            countries (unlike the Selected tier row just below, which is still gated). */}
        <OverviewHeadline
          headlineMovers={headlineMovers}
          scope={`the top ${headlineMovers.length} emitters by ${allCountriesTier.latest_year} output`}
        />
        <TierSummaryPanel
          year={currentYear}
          rows={[
            animatedTierRow('All Countries', allCountriesTier.countries_count, allCountriesTier.co2_by_year, yearIdx),
            animatedTierRow('Expanded (Coverage + ≥100 Mt)', expandedTier.countries_count, expandedTier.co2_by_year, yearIdx),
            ...(selected.length > 0
              ? [animatedTierRow('Selected', selected.length, selectedCo2ByYear, yearIdx)]
              : []),
          ]}
        />
      </div>
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
          headlineMovers={data.headline_movers}
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
