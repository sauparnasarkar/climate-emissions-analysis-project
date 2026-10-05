import { useMemo, useRef, useState, type CSSProperties } from 'react';
import { useLocation } from 'react-router-dom';
import { ClimateKpiStrip } from '../components/overview/ClimateKpiStrip';
import { RelationshipSection } from '../components/overview/RelationshipSection';
import { useClimateSignal } from '../hooks/useClimateSignal';
import { CLIMATE_SIGNAL_ANCHOR, RELATIONSHIP_ANCHOR } from '../lib/climateCopy';
import { sliceMapSeries, worldTotals } from '../lib/mapSeries';
import { KpiStat, ChartCard, SyChart, MultiSelect, Button, InlineAlert, Spinner, Slider, JumpLinks, Table, useReducedMotion } from 'design-system';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useCountUp } from '../hooks/useCountUp';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import { useSelectedCountries } from '../hooks/useCountrySelection';
import { buildHeadlineSentence } from '../lib/overviewHeadline';
import { resolveNoDataColorHex, resolveDivergingScaleReversedHex } from '../lib/resolveThemeColorHex';
import { useThemeColorHex } from '../hooks/useThemeColorHex';
import { BASELINE_YEAR, CLIMATE_SERIES_START_YEAR, MAX_SELECTED_COUNTRIES, POSITIVE_COLOR, NEGATIVE_COLOR } from '../constants';
import { MAGNITUDE_SCALE } from '../lib/magnitudeScale';
import type { MoverRow, OverviewTierMetrics, WorldMapTimeSeries } from '../api/types';

// Stable, hand-authored jump-nav labels (SPEC.md §5.19) -- never copied from a ChartCard's own
// (often dynamic) title. "Map" and "By Country" would otherwise collide if taken verbatim from
// their titles, which share the literal prefix "CO₂ Emissions by Country".
const JUMP_ITEMS: JumpLinkItem[] = [
  { id: 'map', label: 'Map', href: '#map' },
  { id: 'by-country', label: 'By Country', href: '#by-country' },
  { id: 'pct-change', label: '% Change', href: '#pct-change' },
];
// The dashboard header is pinned at the top and 68 px tall (App header minHeight; styles.css offsets every anchor by the same 68). The
// anchor row sticks just below it, so jump targets get that plus the row's own height as their scroll margin.
const STICKY_HEADER_PX = 68;
const JUMP_ROW_PX = 52;

// Area 2's two leading sections come first; "Relationship" only exists while the climate data does.
const CLIMATE_SIGNAL_JUMP: JumpLinkItem = { id: CLIMATE_SIGNAL_ANCHOR, label: 'Climate signal', href: `#${CLIMATE_SIGNAL_ANCHOR}` };
const RELATIONSHIP_JUMP: JumpLinkItem = { id: RELATIONSHIP_ANCHOR, label: 'Relationship', href: `#${RELATIONSHIP_ANCHOR}` };

// Dwell time at each autoplay stop (useYearAnimation steps every 5 years, not by year -- year-
// over-year change is gradual enough to be hard to notice, while a multi-year jump is glaring).
// The KPI tier numbers snap directly to their new value each stop rather than counting up --
// no separate animation duration to coordinate with this one.
const ANIMATION_STOP_MS = 1200;

// A muted neutral clearly outside MAGNITUDE_SCALE's pale-yellow-to-deep-maroon ramp, so a
// no-data country never gets mistaken for a real (if low) value. The old hardcoded '#4a4a4a'
// measured ~1.9:1 against either theme's dark chart panel -- functionally invisible against
// the ocean (Claude Design theme-adherence review, C4). This legend swatch is a plain DOM
// `style` prop, so it can resolve the var() directly; the map itself needs an actual resolved
// hex (see AnimatedWorldMap's noDataColorHex -- Plotly can't parse var(...) at all).
// Card surface for the picker panel -- same tokens TierSummaryPanel/OverviewHeadline use.
const panelStyle: CSSProperties = {
  background: 'var(--__s9cmpx-static-background-standard)',
  border: '1px solid var(--__s9cmpx-static-divider-weak)',
  borderRadius: 8,
  padding: '12px 16px',
};

const NO_DATA_COLOR = 'var(--__s9cmpx-chart-surface-text-weak, #6b7280)';

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
    // accent-tertiary top rule (falls back to transparent on themes that don't publish it, e.g.
    // Dark analytics -- these tokens are Bright/Signal-family only, per the design handoff's
    // "apply per metric, never per sentiment" guidance). Pairs with OverviewHeadline's
    // accent-secondary rule below -- the two hero-row cards read as distinct metric groups.
    <div style={{ background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderTop: '3px solid var(--__s9cmpx-accent-tertiary, transparent)', borderRadius: 8, overflow: 'hidden' }}>
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
// Country names are bolded and increase/decrease values colored (SPEC.md §5.18.6) -- the same
// NEGATIVE_COLOR (increase, bad)/POSITIVE_COLOR (decrease, good) convention TierSummaryPanel's
// own % Change column already uses, so a value here reads consistently with the rest of the
// page rather than introducing a third color rule.
function OverviewHeadline({ headlineMovers, scope }: { headlineMovers: MoverRow[]; scope: string }) {
  const segments = buildHeadlineSentence(headlineMovers, scope);
  if (!segments) return null;
  return (
    // accent-secondary top rule -- see TierSummaryPanel's own comment for the fallback/pairing
    // rationale.
    <div style={{ background: 'var(--__s9cmpx-static-background-standard)', padding: '12px 16px', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderTop: '3px solid var(--__s9cmpx-accent-secondary, transparent)', borderRadius: 8 }}>
      <span className="__s9cmpx-label3" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Since 1990</span>
      <p className="__s9cmpx-body2" style={{ margin: '4px 0 0' }}>
        {segments.map((seg, i) => {
          if (seg.kind === 'country') return <strong key={i}>{seg.text}</strong>;
          if (seg.kind === 'value') {
            return (
              <span key={i} style={{ color: seg.sentiment === 'negative' ? NEGATIVE_COLOR : POSITIVE_COLOR }}>
                {seg.text}
              </span>
            );
          }
          return seg.text;
        })}
      </p>
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
  // SyChart's noDataColor prop feeds Plotly's colorscale directly, which can't resolve a CSS
  // var() -- useThemeColorHex (not a bare resolveNoDataColorHex() call) re-resolves this on
  // every Bright/Dark toggle correctly; a bare call in this render body would race the
  // toggle's own DOM commit and freeze on whichever value it read first (see that hook's
  // comment). noDataColorHex is itself in the memo's deps below, not `theme`, so the memo
  // recomputes exactly when the hook's corrective re-render actually changes the value.
  const noDataColorHex = useThemeColorHex(() => resolveNoDataColorHex('#6b7280'));
  // Autoplay begins when the map scrolls into view rather than on page load.
  const mapRef = useRef<HTMLDivElement>(null);
  const { currentYear, isPlaying, toggle, seek } = useYearAnimation({
    minYear,
    maxYear,
    intervalMs: ANIMATION_STOP_MS,
    startWhenVisible: mapRef,
  });
  const yearIdx = currentYear - minYear;
  // Table view: an accessible, sortable alternative to the map (all countries, current year).
  const [tableView, setTableView] = useState(false);

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
        locationNames: worldMapSeries.countries,
        zLog: true,
        colorValues: worldMapSeries.values[0],
        colorRange: worldMapSeries.value_range,
        noDataColor: noDataColorHex,
        colorScale: MAGNITUDE_SCALE,
        colorbarTitle: 'CO₂ (MtCO₂)',
        hoverUnit: 'MtCO₂',
      },
    ],
    [worldMapSeries, noDataColorHex],
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

  // ISO codes of the picker's selection, outlined on the map. Its own memo (and a separate SyChart
  // prop) so a selection change restyles just the outline and never resets the user's zoom; it
  // only changes when the selection does, not per animation tick.
  const outlineLocations = useMemo(() => selectedIndices.map((i) => worldMapSeries.iso_codes[i]), [selectedIndices, worldMapSeries]);

  // Every country's value for the current year, largest first, no-data last -- the Table view.
  const tableRows = useMemo(() => {
    if (!tableView) return [];
    const row = worldMapSeries.values[yearIdx] ?? [];
    return worldMapSeries.countries
      .map((country, i) => ({ country, v: row[i] ?? null }))
      .sort((a, b) => (b.v ?? -1) - (a.v ?? -1))
      .map(({ country, v }) => ({ country, value: v == null ? 'No data' : v.toLocaleString(undefined, { maximumFractionDigits: v < 10 ? 2 : 0 }) }));
  }, [tableView, worldMapSeries, yearIdx]);

  return (
    <>
      <ChartCard id="map" className="overview-map-card" title={`CO₂ Emissions by Country (${currentYear})`} headingLevel={2} expandable>
        {/* flexWrap + a shrinkable slider track: Slider carries its own 220px min-width,
            which together with the Play/Pause button floored this row (and therefore the
            whole card, and therefore the page) at ~330px -- wider than a 320px phone like
            the Galaxy S9+, forcing horizontal scroll on the entire Overview page. Wrapping
            lets the slider drop to its own line before it has to overflow. */}
        <div style={{ marginBottom: 8, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button variant="ghost-blue" onClick={toggle}>
            {isPlaying ? 'Pause' : 'Play'}
          </Button>
          {/* No `minWidth: 0` here on purpose: Slider hardcodes its own 220px min-width, so
              zeroing this wrapper's floor would let the wrapper shrink while the Slider
              inside overflowed it instead of the row wrapping. Keeping the intrinsic floor
              is what makes flexWrap above actually trigger. */}
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
          <Button variant="ghost-blue" onClick={() => setTableView((v) => !v)} aria-pressed={tableView}>
            {tableView ? 'Map view' : 'Table view'}
          </Button>
        </div>
        {/* No explicit height here, expanded or not -- the choropleth's own ResizeObserver
            already recomputes height from container width alone (SPEC.md §5.10), so widening
            the container on expand is sufficient. Coexists with SyChart's own internal
            "Reset view" control (a different button, in a different location). */}
        {/* Hidden, not unmounted, in Table view: remounting would throw away the user's map zoom and
            re-run the whole choropleth draw. SyChart's own ResizeObserver resizes it on return. */}
        <div ref={mapRef} style={{ display: tableView ? 'none' : undefined }}>
        <SyChart
          showLegend={false}
          ariaLabel={`Animated world map choropleth of CO₂ emissions by country, ${minYear} to ${maxYear}, currently showing ${currentYear}, log-scaled color from light (lowest) to deep red (highest)`}
          series={series}
          animationFrame={{ colorValues: worldMapSeries.values[yearIdx] }}
          outlineLocations={outlineLocations}
        />
        </div>
        {tableView && (
          <div style={{ maxHeight: 420, overflow: 'auto' }} tabIndex={0} role="region" aria-label={`CO₂ by country, ${currentYear}, table view`}>
            <Table
              size="small"
              caption={`CO₂ by country, ${currentYear} (MtCO₂) — all ${worldMapSeries.countries.length} countries`}
              columns={[
                { key: 'country', header: 'Country', sortable: true },
                { key: 'value', header: 'MtCO₂', align: 'right' },
              ]}
              rows={tableRows}
            />
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px 16px', marginTop: 8 }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: NO_DATA_COLOR, display: 'inline-block' }} />
            <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
              Gray = no CO₂ data reported for that country in {currentYear}
            </span>
          </span>
          {outlineLocations.length > 0 && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, border: '2px solid var(--__s9cmpx-color-brand-500)', boxSizing: 'border-box', display: 'inline-block' }} />
              <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Outlined = your selected countries</span>
            </span>
          )}
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
  // URL-backed (?countries=…, SPEC.md §5.25) so links can open with a chosen selection.
  const [selected, setSelected] = useSelectedCountries(featured, expanded);
  // Still fires even when selected is empty (client.ts omits the query param, server
  // defaults to FEATURED_COUNTRIES) — matches HistoricalTrendsPage's exact precedent. The
  // Selected tier/charts/movers below are gated on the *local* selected.length, not on
  // whatever the server happened to default to, so an empty selection reliably shows the
  // warning regardless of what data resolves to.
  const { data, error, loading } = useAsync(() => api.overview(selected), [selected.join(',')]);
  // Selection-invariant -- deps: [] means this fires exactly once for the page's lifetime,
  // regardless of how many times `selected` changes (SPEC.md §5.17.1).
  // One request for the longer 1970 range (the climate chart and sparklines use it); the 1990-based series the map plays is sliced from it,
  // so the map itself is unchanged until its own step extends it.
  const { data: globeSeries, error: worldMapError, loading: worldMapLoading } = useAsync(() => api.worldMapSeries(CLIMATE_SERIES_START_YEAR), []);
  const worldMapSeries = useMemo(() => (globeSeries ? sliceMapSeries(globeSeries, BASELINE_YEAR) : null), [globeSeries]);
  const climate = useClimateSignal();
  const emissionsSeries = useMemo(() => (globeSeries ? worldTotals(globeSeries).map((value, i) => ({ year: globeSeries.years[i], value })) : []), [globeSeries]);
  const reduceMotion = useReducedMotion();
  // Called here (unconditionally, ahead of the early returns below) rather than at the % Change
  // chart's render site — Rules of Hooks. See resolveDivergingScaleReversedHex's own comment for
  // why this chart needs a reversed stop order instead of SyChart's default diverging scale.
  const moverColorScale = useThemeColorHex(() => resolveDivergingScaleReversedHex());
  // Handles a bookmarked/shared #anchor already in the URL (SPEC.md §5.19) -- called
  // unconditionally (before the early returns below) per the Rules of Hooks; the hook itself
  // only actually jumps once `data`/`worldMapSeries` (and therefore the jump targets) exist.
  // A deep link to #relationship must wait for the climate request to actually finish: that section only exists with its data, and the
  // hook jumps once only. (Any other hash jumps as soon as the page renders, which is bounded by the timeout.)
  const { hash } = useLocation();
  const waitsForClimate = hash === `#${RELATIONSHIP_ANCHOR}`;
  useJumpToHashOnLoad(Boolean(data && worldMapSeries && climate.settled && (!waitsForClimate || climate.done)), reduceMotion);

  // useAsync preserves the previous `data` while a refetch is in flight (only `loading`
  // flips), so only block on a spinner before anything has ever loaded — once `data`
  // exists, keep the picker/last-good UI mounted across every selection change instead of
  // unmounting the whole page (and its MultiSelect) on every refetch.
  if (error || worldMapError) return <InlineAlert variant="warning">{error ?? worldMapError}</InlineAlert>;
  if (!data || !worldMapSeries || !climate.settled) return loading || worldMapLoading || !climate.settled ? <Spinner /> : null;

  const barSeries = data.latest_year_bar.map((c) => c.country);
  const barValues = data.latest_year_bar.map((c) => c.value ?? 0);

  const moverCountries = data.top_movers.map((m) => m.country);
  const moverPct = data.top_movers.map((m) => m.pct_change ?? 0);
  // Symmetric around zero so 0% change always lands on the reversed scale's true midpoint
  // (mid-tone) stop -- required once an explicit colorScale is passed, since SyChart's own
  // `cmid: 0` zero-centering only applies to its own default scale (see the series prop below).
  // The `1` floor guards the degenerate all-zero case (a real Plotly colorRange can't span [0, 0]).
  const moverPctMaxAbs = Math.max(1, ...moverPct.map((v) => Math.abs(v)));

  return (
    <div className="overview-page">
      {/* Overrides styles.css's global 68 px anchor offset for this page: the header AND the sticky anchor row both sit above a jump target. */}
      <style>{`.overview-page [id] { scroll-margin-top: ${STICKY_HEADER_PX + JUMP_ROW_PX}px; }`}</style>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Overview</h1>
      {/* Breathing room below the jump links: the active link's underline used to sit flush against the
          map card's accent top rule (and its shadow), reading as one muddled line. */}
      {/* Sticks to the top while the page scrolls (requirements §2.2 wireframes: anchor / deep-link support). */}
      <div style={{ marginBottom: 16, position: 'sticky', top: STICKY_HEADER_PX, zIndex: 5, background: 'var(--__s9cmpx-static-background-weak)', padding: '4px 0' }}>
        <JumpLinks items={[CLIMATE_SIGNAL_JUMP, ...(climate.signal ? [RELATIONSHIP_JUMP] : []), ...JUMP_ITEMS]} />
      </div>

      <section id={CLIMATE_SIGNAL_ANCHOR} aria-labelledby="climate-signal-heading" style={{ marginBottom: 16 }}>
        <h2 id="climate-signal-heading" className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>What is happening globally</h2>
        <ClimateKpiStrip
          emissions={{
            year: data.all_countries.latest_year,
            total: data.all_countries.latest_co2_total,
            pctChange: data.all_countries.pct_change_since_1990,
            baselineYear: BASELINE_YEAR,
            series: emissionsSeries,
          }}
          signal={climate.signal}
          mean5y={climate.mean5y}
        />
      </section>
      {climate.signal && <RelationshipSection signal={climate.signal} emissionsSeries={emissionsSeries} />}

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

      {/* id lives here, not on the "By Country" heading below -- this picker sits above that
          heading (it's shared with the % Change section further down), so anchoring "by-country"
          to the heading alone left the picker itself scrolled out of view above the jump
          target, confirmed live: the dropdown a user needs to change their selection wasn't
          visible after following the link. Anchoring the wrapping row instead means the picker
          is the first thing on screen, exactly what "By Country" should feel like it jumps to. */}
      <section id="by-country" aria-labelledby="picker-heading" style={{ ...panelStyle, marginBottom: 16 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '4px 12px', marginBottom: 12 }}>
          <h2 id="picker-heading" className="__s9cmpx-headline6" style={{ margin: 0 }}>Selected countries</h2>
          <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
            {selected.length} of {MAX_SELECTED_COUNTRIES} max · from the {expanded.length} Expanded countries · drives the Selected tier and every chart below
          </span>
        </div>
        <div className="country-picker-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12 }}>
          <MultiSelect
            label={`Select countries (up to ${MAX_SELECTED_COUNTRIES}/${expanded.length})`}
            options={expanded.map((c) => ({ value: c, label: c }))}
            value={selected}
            onChange={setSelected}
            maxSelected={MAX_SELECTED_COUNTRIES}
          />
          <Button variant="ghost-blue" onClick={() => setSelected(featured)}>Reset to default</Button>
        </div>
      </section>

      {/* By Country and Top Movers side by side, both driven by the selection. Heading lives outside
          the selected.length gate (matching HistoricalTrendsPage's own pattern) -- previously this
          whole block was one InlineAlert-or-fragment ternary with no persistent element to anchor
          to when deselected to 0. */}
      <style>{'@media (max-width: 1100px) { .overview-country-grid { grid-template-columns: 1fr !important; } }'}</style>
      <div className="overview-country-grid" style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <div style={{ minWidth: 0 }}>
          <h2 className="__s9cmpx-headline6" style={{ margin: '8px 0 12px' }}>By Country</h2>
          {selected.length === 0 ? (
            <InlineAlert variant="warning">Select at least one country.</InlineAlert>
          ) : (
            <ChartCard title={`CO₂ Emissions by Country (${data.selected.latest_year})`} headingLevel={3}>
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
          )}
        </div>

        {selected.length > 0 && (
          <section aria-labelledby="movers-heading" style={{ minWidth: 0 }}>
            <h2 id="movers-heading" className="__s9cmpx-headline6" style={{ margin: '8px 0 4px' }}>Top Movers Since 1990 ({data.selected_country_list.length} Selected Countries)</h2>
            <p className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)', margin: '0 0 12px' }}>
              Fastest growth and largest reduction in CO₂ emissions, 1990 → {data.selected.latest_year}, among the {data.selected_country_list.length} selected countries.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* deltaColor overrides KpiStat's own internal red/green good/bad lookup with the
                  same brown/teal pair the % Change chart below and the narrative panel above use
                  (Claude Design theme-adherence review round 2) -- deltaDirection is kept as-is
                  alongside it purely for the glyph (warning/check), the redundant non-color cue
                  this pair needs given its low (~1.2:1) mutual contrast. */}
              <KpiStat
                card
                label={`Fastest Growth — ${data.fastest_growth.country}`}
                value={<CountUpText value={data.fastest_growth.pct_change ?? 0} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} />}
                delta={`${(data.fastest_growth.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.fastest_growth.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="bad"
                deltaColor={NEGATIVE_COLOR}
              />
              <KpiStat
                card
                label={`Largest Reduction — ${data.largest_reduction.country}`}
                value={<CountUpText value={data.largest_reduction.pct_change ?? 0} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} />}
                delta={`${(data.largest_reduction.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.largest_reduction.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="good"
                deltaColor={POSITIVE_COLOR}
              />
            </div>
          </section>
        )}
      </div>

      {/* Always rendered (even with 0 selected) so #pct-change stays a real jump target (SPEC.md §5.19). */}
      <div id="pct-change" style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6" style={{ margin: '0 0 12px' }}>% Change Since 1990</h2>
        {selected.length === 0 ? (
          <InlineAlert variant="warning">Select at least one country.</InlineAlert>
        ) : (
          <ChartCard title={`CO₂ % Change by Country, 1990–${data.selected.latest_year}`} headingLevel={3}>
            {/* Legend for the diverging pair: brown = increase (bad), teal = decrease (good) -- the
                chart's own colorbar shows the gradient, this names the two ends in words. */}
            <div className="__s9cmpx-body4" style={{ display: 'flex', gap: 16, marginBottom: 8, color: 'var(--__s9cmpx-static-text-weak)' }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: NEGATIVE_COLOR, display: 'inline-block' }} /> Increase
              </span>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2, background: POSITIVE_COLOR, display: 'inline-block' }} /> Decrease
              </span>
            </div>
            <SyChart
              height={320}
              xTitle="Country"
              yTitle={`% Change in CO₂ (1990→${data.selected.latest_year})`}
              showLegend={false}
              ariaLabel={`Bar chart of percent change in CO₂ emissions from 1990 to ${data.selected.latest_year} for ${moverCountries.length} countries, colored on a diverging scale from a decrease (favorable) at one end to an increase (unfavorable) at the other`}
              series={[{
                name: '% Change',
                x: moverCountries,
                y: moverPct,
                kind: 'bar',
                colorValues: moverPct,
                colorScale: moverColorScale,
                colorRange: [-moverPctMaxAbs, moverPctMaxAbs],
                colorbarTitle: `% Change in CO₂ (1990→${data.selected.latest_year})`,
              }]}
            />
          </ChartCard>
        )}
      </div>
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
