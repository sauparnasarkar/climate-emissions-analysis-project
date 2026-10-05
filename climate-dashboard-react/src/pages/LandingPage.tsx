import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Globe, Icon, InlineAlert, Slider } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useThemeColorHex } from '../hooks/useThemeColorHex';
import { useViewportHeight } from '../hooks/useViewportHeight';
import { useYearAnimation } from '../hooks/useYearAnimation';
import { RankRace } from '../components/landing/RankRace';
import { CLIMATE_BANNER_STYLES, ClimateSignalBanner } from '../components/landing/ClimateSignalBanner';
import { CAROUSEL_STYLES, HeroCarousel } from '../components/landing/HeroCarousel';
import { ctaClass } from '../components/landing/cta';
import { buildClimateSignal } from '../lib/climateSignal';
import { sliceMapSeries, worldTotals } from '../lib/mapSeries';
import { ChainBand } from '../components/landing/ChainBand';
import {
  FORECAST_END_YEAR, MAX_SELECTED_COUNTRIES, NEGATIVE_COLOR, POSITIVE_COLOR, SCENARIO_END_YEAR, SCENARIO_START_YEAR,
} from '../constants';
import { fmtInt, fmtPct, pickStories, sparklinePath, type Story } from '../lib/landingData';
import { MAGNITUDE_SCALE } from '../lib/magnitudeScale';
import { resolveNoDataColorHex } from '../lib/resolveThemeColorHex';
import { NAV_ITEMS } from '../navigation';
import type { OverviewResponse, WorldMapTimeSeries } from '../api/types';

// Landing page (Release 20, SPEC.md §5.25). Every number and year on it is computed from the API's
// own responses (/overview, /overview/world-map-series) -- nothing is typed in -- so a weekly data
// refresh that moves the latest year or country counts updates the page with no code change.

// The landing globe is ambient (requirements §2.6, ENHANCEMENTS.md decision 12): it turns once, continuously, while the year
// advances one at a time from GLOBE_START_YEAR to the latest, blending colours between years so the change reads as smooth
// rather than stepped. ~700 ms a year, ~40 s for the whole pass. (Release 20's decade-by-decade steps are replaced.)
// The legend, controls, slider and total stay visible throughout; only the per-country labels are hidden while it plays.
const GLOBE_START_YEAR = 1970;
const GLOBE_STEP_MS = 700;
const GLOBE_STEP_YEARS = 1;
// The rest of the landing page (stories, rank race, KPIs) still reads from 1990, the project's baseline year.
const BASELINE_YEAR = 1990;

// How long the page waits, once the overview and map are ready, for the optional climate-signal data before settling on
// the existing hero alone (api/client.ts's fetch has no timeout, so a stalled request must not hold the page back).
const CLIMATE_WAIT_MS = 3000;

// Same starter the agent page offers, so this card promises something the agent demonstrably does.
const AGENT_EXAMPLE = 'How has India’s emissions grown compared to other countries?';

const STYLES = `
.landing { --landing-pad-x: clamp(20px, 5.5vw, 80px); --landing-pad-y: clamp(48px, 6vw, 88px); }
.landing-h2 { font-size: clamp(1.75rem, 3.2vw, 2.75rem); line-height: 1.1; font-weight: 600; }
.landing-hero { display: flex; gap: clamp(32px, 4vw, 56px); align-items: center; padding: clamp(16px, 3vh, 48px) var(--landing-pad-x); }
.landing-hero__text { flex: 0 0 min(540px, 46%); min-width: 0; display: flex; flex-direction: column; gap: clamp(12px, 2.2vh, 24px); }
.landing-hero__globe { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.landing-hero__controls { width: 100%; max-width: 624px; display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.landing-globe-title--block { display: none; width: 100%; max-width: 624px; }
.landing-kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid var(--__s9cmpx-static-divider-weak); margin-top: 8px; }
.landing-grid3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; }
.landing-race { display: flex; gap: clamp(32px, 5vw, 80px); align-items: flex-start; }
.landing-race__text { flex: 0 0 min(380px, 34%); }
.landing-race__chart { flex: 1 1 0; min-width: 0; }
@media (max-width: 1100px) {
  .landing-hero, .landing-race { flex-direction: column; align-items: stretch; }
  .landing-hero__text, .landing-race__text { flex: none; }
  .landing-grid3 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
  .landing-globe-title--block { display: block; }
  .landing-globe-title--overlay { display: none; }
  .landing-grid3 { grid-template-columns: 1fr; }
  /* The hero banner on phones (decision 72): the three KPIs stay in one row, the buttons are full-width and stacked. */
  .landing-hero { gap: 16px; padding-top: 12px; padding-bottom: 8px; }
  .landing-hero__text > p { font-size: 0.9375rem !important; line-height: 1.45; }
  .landing-kpis > div { padding: 12px 8px 0 12px !important; }
  .landing-kpis > div:first-child { padding-left: 0 !important; }
  .landing-kpis > div > div:first-child { font-size: 1.125rem !important; }
  .landing-kpis .__s9cmpx-body3 { font-size: 12px; line-height: 1.3; }
  /* Same order as the climate banner (decision 73): copy, figures, picture, then the buttons -- so the buttons come after the globe. */
  .landing-hero__text { display: contents !important; }
  .landing-hero__text > *, .landing-hero__globe { order: 0; }
  .landing-hero__globe { order: 5; }
  .landing-hero__ctas { order: 6; flex-direction: column; }
  .landing-hero__ctas > a { justify-content: center; }
}
`;

const cardStyle = {
  padding: 28, borderRadius: 16, background: 'var(--__s9cmpx-static-background-standard)',
  border: '1px solid var(--__s9cmpx-static-divider-weak)', display: 'flex', flexDirection: 'column', gap: 12,
} as const;

function Kpi({ value, label, color, border }: { value: string; label: string; color?: string; border: boolean }) {
  return (
    <div style={{ padding: border ? '20px 16px 0 20px' : '20px 16px 0 0', borderLeft: border ? '1px solid var(--__s9cmpx-static-divider-weak)' : undefined, minWidth: 0 }}>
      <div style={{ fontSize: 'clamp(1.25rem, 2.2vw, 1.75rem)', fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      <div className="__s9cmpx-body3" style={{ color: 'var(--__s9cmpx-static-text-weak)', marginTop: 4 }}>{label}</div>
    </div>
  );
}

// Own component so the ~5s year-steps re-render only the hero, never the stories/race/feature cards.
function Hero({ overview, map, globe, active = true }: { overview: OverviewResponse; map: WorldMapTimeSeries; globe: WorldMapTimeSeries; active?: boolean }) {
  // `map` is the 1990-based view the KPIs and "change since" use; `globe` is the longer 1970 series the animation plays.
  const baselineYear = map.years[0];
  const minYear = globe.years[0];
  const maxYear = globe.years[globe.years.length - 1];
  // Autoplay begins when the globe scrolls into view, not on page load (e.g. below the fold on a phone).
  const globeRef = useRef<HTMLDivElement>(null);
  const { currentYear, isPlaying, toggle, seek } = useYearAnimation({ minYear, maxYear, intervalMs: GLOBE_STEP_MS, stepYears: GLOBE_STEP_YEARS, startWhenVisible: globeRef, enabled: active });
  const yearIdx = currentYear - minYear;
  const all = overview.all_countries;
  const noDataColorHex = useThemeColorHex(() => resolveNoDataColorHex('#6b7280'));
  // Size the globe so the slide plus the carousel controls fit above the fold on a laptop: the viewport minus the 68 px
  // header, ~64 px of carousel controls, the section's own padding, the legend and globe controls under the canvas, and the
  // Pause/year-slider row.
  const viewportHeight = useViewportHeight();
  const globeMax = Math.max(300, Math.min(600, viewportHeight - 68 - 64 - 56 - 100 - 52));
  const totals = useMemo(() => worldTotals(globe), [globe]);
  const yearTotal = totals[yearIdx];
  // The current year and world total. On wide screens it overlays the globe's top-left corner; on a phone the globe is
  // small and centred, so the overlay would sit on the dark disc (dark text on a dark ocean) -- there it is shown
  // above the globe instead (CSS below swaps which copy is displayed; the hidden one is display:none, so it is not
  // in the accessibility tree twice).
  const globeHeading = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span style={{ fontSize: 28, fontWeight: 600, lineHeight: 1, fontVariantNumeric: 'tabular-nums', color: 'var(--__s9cmpx-static-text-strong)' }}>{currentYear}</span>
        {yearTotal != null && (
          // Two short lines rather than one long one: the overlay sits in the globe box's top-left corner, and
          // "22,899 MtCO₂ · all countries" at this size ran into the disc's edge.
          <>
            <span className="__s9cmpx-body3" style={{ color: 'var(--__s9cmpx-static-text-standard)', fontVariantNumeric: 'tabular-nums' }}>{fmtInt(yearTotal)} MtCO₂</span>
            <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-standard)' }}>all countries</span>
          </>
        )}
      </div>
  );

  return (
    <section aria-labelledby="landing-title" className="landing-hero">
      <div className="landing-hero__text">
        <div className="__s9cmpx-label3" style={{ letterSpacing: '0.08em', lineHeight: 1.5, textTransform: 'uppercase', color: 'var(--__s9cmpx-static-text-accent, inherit)' }}>
          Our World in Data CO₂ · {minYear}–{maxYear} · {all.countries_count} countries
        </div>
        <h1 id="landing-title" style={{ margin: 0, fontSize: 'clamp(1.75rem, min(4.6vw, 5.8vh), 3.75rem)', lineHeight: 1.05, fontWeight: 700 }}>
          Where the world’s CO₂ comes from — and where it’s heading.
        </h1>
        <p className="__s9cmpx-body1" style={{ margin: 0, fontSize: 'clamp(1rem, 1.4vw, 1.125rem)', color: 'var(--__s9cmpx-static-text-weak)' }}>
          Emissions for {all.countries_count} countries since {minYear}, ETS(A,Ad,N) forecasts to {FORECAST_END_YEAR} and scenario pathways to {SCENARIO_END_YEAR} — with an AI agent that answers questions from the same data.
        </p>
        <div className="landing-hero__ctas" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link to="/overview" className={ctaClass('primary')} style={{ textDecoration: 'none' }}>
            Explore the data <Icon name="expand" size={16} />
          </Link>
          <Link to="/forecasts" className={ctaClass('secondary')} style={{ textDecoration: 'none' }}>Forecasts to {FORECAST_END_YEAR}</Link>
        </div>
        <div className="landing-kpis">
          <Kpi border={false} value={fmtInt(all.latest_co2_total)} label={`MtCO₂ in ${all.latest_year}, all countries`} />
          <Kpi border value={fmtPct(all.pct_change_since_1990)} label={`Change since ${baselineYear}`} color={all.pct_change_since_1990 >= 0 ? NEGATIVE_COLOR : POSITIVE_COLOR} />
          <Kpi border value={String(overview.expanded_countries.countries_count)} label="Countries in the Expanded set" />
        </div>
      </div>

      <div className="landing-hero__globe" ref={globeRef}>
        <div className="landing-globe-title--block">{globeHeading}</div>
        <Globe
          isoCodes={globe.iso_codes}
          locationNames={globe.countries}
          years={globe.years}
          values={globe.values}
          yearIndex={yearIdx}
          colorRange={globe.value_range}
          colorScale={MAGNITUDE_SCALE}
          zLog
          noDataColor={noDataColorHex}
          hoverUnit="MtCO₂"
          legendTitle="CO₂ (MtCO₂)"
          noDataLabel="Gray = no data"
          ariaLabel={`Globe of CO₂ emissions by country, ${minYear} to ${maxYear}, log-scaled colour from light (lowest) to deep red (highest)`}
          // Rotation follows the same play/pause as the year animation, so Pause (or a manual seek, which
          // pauses) stops the whole hero -- not just the year.
          autoRotate={isPlaying}
          // With Reduce Motion on there is no autoplay, but the user's own Play press is a request for movement:
          // the globe spins while it runs (colour blending stays off, years just step).
          allowSpinWithReducedMotion
          // One full turn across the whole pass, so the rotation is continuous rather than one turn per year-step.
          rotationPeriodMs={Math.max(1, globe.years.length - 1) * GLOBE_STEP_MS}
          // Colours blend over the whole year-step (none under reduced motion, which Globe forces itself).
          blendMs={GLOBE_STEP_MS}
          // The legend, the globe's own controls, the year slider and the total are always shown (owner decision, 2026-10-04,
          // amending requirements §2.6). Only the per-country MtCO₂ labels depend on motion: they would be unreadable on a
          // spinning globe, so they appear when it stops.
          showLabels={!isPlaying}
          maxSize={globeMax}
          transparent
          title={<div className="landing-globe-title--overlay">{globeHeading}</div>}
        />
        <div className="landing-hero__controls">
          <Button variant="ghost-blue" onClick={toggle}>{isPlaying ? 'Pause' : 'Play'}</Button>
          <div style={{ flex: 1 }}>
            <Slider label="Year" min={minYear} max={maxYear} step={1} value={currentYear} onChange={seek} showValue={false} showRangeLabels />
          </div>
        </div>
      </div>
    </section>
  );
}

// `to`/`cta` take the story's country: the first two links deep-link (?country= / ?countries=, see
// useCountrySelection) so the card's promise -- "Open China's profile" -- is what actually opens.
// The last has no country parameter: the Overview's % Change chart covers the *selected* countries,
// and one country isn't a comparison.
const STORY_COPY: Record<Story['kind'], { kicker: string; text: (n: number, since: number) => string; cta: (c: string) => string; to: (c: string) => string }> = {
  'largest-rise': { kicker: 'largest absolute rise', text: (n, since) => `MtCO₂ added since ${since}, the largest increase of any top-${n} emitter.`, cta: (c) => `Open ${c}’s profile`, to: (c) => `/country-profile?country=${encodeURIComponent(c)}` },
  'fastest-growth': { kicker: 'fastest growth', text: (n, since) => `The fastest percentage growth among the top-${n} emitters since ${since}.`, cta: (c) => `See ${c} in Historical Trends`, to: (c) => `/historical?countries=${encodeURIComponent(c)}` },
  'steepest-decline': { kicker: 'steepest decline', text: (n, since) => `The steepest cut among the top-${n} emitters since ${since}.`, cta: () => 'See % change on the Overview', to: () => '/overview#pct-change' },
};

function StoryCard({ story, topN, firstYear, lastYear }: { story: Story; topN: number; firstYear: number; lastYear: number }) {
  const copy = STORY_COPY[story.kind];
  const color = story.sentiment === 'increase' ? NEGATIVE_COLOR : POSITIVE_COLOR;
  const path = sparklinePath(story.series);
  return (
    <article style={{ ...cardStyle, padding: 32, gap: 16 }}>
      <div className="__s9cmpx-label3" style={{ letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--__s9cmpx-static-text-weak)' }}>
        {story.country} · {copy.kicker}
      </div>
      <div style={{ fontSize: 'clamp(2rem, 3.4vw, 3rem)', fontWeight: 600, color, fontVariantNumeric: 'tabular-nums' }}>{story.headline}</div>
      <div className="__s9cmpx-body2">{copy.text(topN, firstYear)}</div>
      {path && (
        <svg width="100%" height="64" viewBox="0 0 300 64" preserveAspectRatio="none" role="img" aria-label={`${story.country} CO₂ emissions, ${firstYear} to ${lastYear}`}>
          <path d={path} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        </svg>
      )}
      {story.from != null && story.to != null && (
        <div className="__s9cmpx-body4" style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--__s9cmpx-static-text-weak)', fontVariantNumeric: 'tabular-nums' }}>
          <span>{firstYear} · {fmtInt(story.from)}</span>
          <span>{lastYear} · {fmtInt(story.to)}</span>
        </div>
      )}
      <Link to={copy.to(story.country)} style={{ fontWeight: 600, color: 'var(--__s9cmpx-static-text-accent, inherit)' }}>{copy.cta(story.country)} →</Link>
    </article>
  );
}

function Stories({ overview, map }: { overview: OverviewResponse; map: WorldMapTimeSeries }) {
  const stories = useMemo(() => pickStories(overview.headline_movers, map), [overview.headline_movers, map]);
  if (stories.length === 0) return null;
  const firstYear = map.years[0];
  const lastYear = map.years[map.years.length - 1];
  const topN = overview.headline_movers.length;
  return (
    <section aria-labelledby="stories-heading" style={{ padding: 'var(--landing-pad-y) var(--landing-pad-x)', background: 'var(--__s9cmpx-static-background-standard)', display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <h2 id="stories-heading" className="landing-h2" style={{ margin: 0 }}>
          {stories.length === 3 ? 'Three' : stories.length === 2 ? 'Two' : 'One'} {stories.length === 1 ? 'story' : 'stories'} in {map.years.length} years of data
        </h2>
        <p className="__s9cmpx-body2" style={{ margin: 0, color: 'var(--__s9cmpx-static-text-weak)' }}>
          Among the {topN} largest emitters of {lastYear}, {firstYear} → {lastYear}.
        </p>
      </div>
      <div className="landing-grid3">
        {stories.map((s) => <StoryCard key={s.kind} story={s} topN={topN} firstYear={firstYear} lastYear={lastYear} />)}
      </div>
    </section>
  );
}

function featureText(id: string, overview: OverviewResponse, map: WorldMapTimeSeries): string {
  const first = map.years[0];
  const last = map.years[map.years.length - 1];
  const expanded = overview.expanded_countries.countries_count;
  switch (id) {
    case 'overview': return `World map, the three-tier summary and a ${MAX_SELECTED_COUNTRIES}-country picker driving the By Country and % Change charts.`;
    case 'historical': return `Compare up to ${MAX_SELECTED_COUNTRIES} countries across ${first}–${last}, with gas composition by decade.`;
    case 'country-profile': return 'Total, per-capita and year-on-year CO₂ for one country, with key statistics.';
    case 'data-explorer': return 'Browse and filter the underlying dataset, with summary statistics.';
    case 'climate-correlation': return 'Emissions, atmospheric CO₂ and global temperature side by side: how they move together over time, shown as context rather than a climate model.';
    case 'forecasts': return `ETS(A,Ad,N) forecasts to ${FORECAST_END_YEAR} for all ${expanded} Expanded countries, with 95% confidence bands, benchmarked against Linear Regression and Random Forest.`;
    case 'scenarios': return `BAU, Moderate and Aggressive pathways to ${SCENARIO_END_YEAR}, with cumulative ${SCENARIO_START_YEAR}–${SCENARIO_END_YEAR} totals.`;
    default: return '';
  }
}

function Features({ overview, map }: { overview: OverviewResponse; map: WorldMapTimeSeries }) {
  // The About page isn't a feature; every other nav entry is.
  const items = NAV_ITEMS.filter((item) => item.group);
  return (
    <section aria-labelledby="features-heading" style={{ padding: 'var(--landing-pad-y) var(--landing-pad-x)', background: 'var(--__s9cmpx-static-background-standard)', display: 'flex', flexDirection: 'column', gap: 32 }}>
      <h2 id="features-heading" className="landing-h2" style={{ margin: 0 }}>Everything you need to read the trend</h2>
      <div className="landing-grid3">
        {items.map((item) => (
          <Link key={item.id} to={item.path} style={{ ...cardStyle, background: 'var(--__s9cmpx-static-background-weak)', color: 'inherit', textDecoration: 'none' }}>
            <div className="__s9cmpx-label3" style={{ letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--__s9cmpx-static-text-weak)' }}>{item.group}</div>
            <div style={{ fontSize: 20, fontWeight: 600 }}>{item.label}</div>
            <div className="__s9cmpx-body2">{featureText(item.id, overview, map)}</div>
          </Link>
        ))}
      </div>
      <Link to="/ask" style={{ ...cardStyle, flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 20, background: 'var(--__s9cmpx-static-background-weak)', color: 'inherit', textDecoration: 'none' }}>
        <Icon name="sparkle" size={32} />
        <div style={{ flex: '1 1 260px', minWidth: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 600 }}>Ask the Agent</div>
          <div className="__s9cmpx-body2">“{AGENT_EXAMPLE}” — answered with charts from the same API the dashboard uses.</div>
        </div>
        <span style={{ fontWeight: 600, color: 'var(--__s9cmpx-static-text-accent, inherit)' }}>Ask a question →</span>
      </Link>
    </section>
  );
}

function BuiltOn() {
  return (
    <section aria-label="Built on" style={{ padding: '40px var(--landing-pad-x)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '16px 48px', borderTop: '1px solid var(--__s9cmpx-static-divider-weak)', borderBottom: '1px solid var(--__s9cmpx-static-divider-weak)' }}>
      <div className="__s9cmpx-label3" style={{ letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--__s9cmpx-static-text-weak)' }}>Built on</div>
      <ul style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 40px', listStyle: 'none', margin: 0, padding: 0 }}>
        {['Our World in Data · CO₂', 'Linear Regression', 'Random Forest', 'ETS(A,Ad,N)', 'MCP agent tools'].map((t) => <li key={t} className="__s9cmpx-body2">{t}</li>)}
      </ul>
    </section>
  );
}

function ClosingCta({ expandedCount }: { expandedCount: number }) {
  return (
    <section aria-labelledby="cta-heading" style={{ padding: 'var(--landing-pad-y) var(--landing-pad-x)', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 24 }}>
      <h2 id="cta-heading" className="landing-h2" style={{ margin: 0, maxWidth: 900 }}>Pick a country. See where it’s heading.</h2>
      <p className="__s9cmpx-body1" style={{ margin: 0, maxWidth: 600, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Start on the Overview, drill into any of the {expandedCount} Expanded countries, and compare forecasts to {FORECAST_END_YEAR} and scenarios to {SCENARIO_END_YEAR}.
      </p>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        <Link to="/overview" className={ctaClass('primary')} style={{ textDecoration: 'none' }}>Open the Overview</Link>
        <Link to="/about" className={ctaClass('secondary')} style={{ textDecoration: 'none' }}>About the methodology</Link>
      </div>
    </section>
  );
}

export default function LandingPage() {
  const overview = useAsync(() => api.overview(), []);
  // One request, for the globe's longer range; the 1990-based view the rest of the page uses is sliced from it.
  const globeQuery = useAsync(() => api.worldMapSeries(GLOBE_START_YEAR), []);
  const globe = globeQuery.data;
  const map = useMemo(() => (globe ? sliceMapSeries(globe, BASELINE_YEAR) : null), [globe]);
  // The climate-signal banner (Area 2) is additive: if any of its three series is missing or fails to load, the page is
  // the existing hero on its own -- never a banner with zeros or gaps. Waited for (settled either way) before the hero
  // mounts, so the hero never remounts -- and the globe never restarts -- when the carousel appears.
  const climate = useAsync(async () => {
    const [pair, temperature, concentration] = await Promise.all([
      api.correlationEmissionsTemperature(),
      api.correlationTemperature({ baseline: '1850_1900' }),
      api.correlationConcentration(),
    ]);
    return buildClimateSignal(pair, temperature, concentration);
  }, []);
  const coreReady = Boolean(overview.data && globe);
  const [climateGaveUp, setClimateGaveUp] = useState(false);
  useEffect(() => {
    if (!coreReady || !climate.loading) return;
    const id = setTimeout(() => setClimateGaveUp(true), CLIMATE_WAIT_MS);
    return () => clearTimeout(id);
  }, [coreReady, climate.loading]);
  const error = overview.error ?? globeQuery.error;
  const ready = coreReady && (!climate.loading || climateGaveUp);
  // Once given up on, a late answer is ignored for good: adding the carousel then would remount the hero and restart the globe.
  const signal = climateGaveUp ? null : climate.data;

  return (
    <div className="landing">
      <style>{STYLES + CAROUSEL_STYLES + CLIMATE_BANNER_STYLES}</style>
      {ready ? (
        <>
          {signal ? (
            <HeroCarousel
              slides={[
                { id: 'climate-signal', label: 'Climate signal', render: () => <ClimateSignalBanner signal={signal} headingId="climate-signal-title" /> },
                { id: 'where-co2-comes-from', label: 'Where CO₂ comes from', render: (active) => <Hero overview={overview.data!} map={map!} globe={globe!} active={active} /> },
              ]}
            />
          ) : (
            <Hero overview={overview.data!} map={map!} globe={globe!} />
          )}
          {signal && (
            <ChainBand
              signal={signal}
              emissions={{
                year: overview.data!.all_countries.latest_year,
                total: overview.data!.all_countries.latest_co2_total,
                // Annual world totals over the globe's whole range, from the same series the globe plays.
                series: worldTotals(globe!).map((value, i) => ({ year: globe!.years[i], value })),
              }}
            />
          )}
          <Stories overview={overview.data!} map={map!} />
          <RankRace series={map!} worldTotals={overview.data!.all_countries.co2_by_year} expandedCount={overview.data!.expanded_countries.countries_count} />
          <Features overview={overview.data!} map={map!} />
          <BuiltOn />
          <ClosingCta expandedCount={overview.data!.expanded_countries.countries_count} />
        </>
      ) : (
        // The headline and the way in stay put while (or if) the data can't load -- the page is
        // never blank, and the CTAs still reach the dashboard.
        <section aria-labelledby="landing-title" style={{ padding: 'clamp(32px, 4vw, 56px) var(--landing-pad-x)', display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 800 }}>
          <h1 id="landing-title" style={{ margin: 0, fontSize: 'clamp(2.25rem, 4.6vw, 3.75rem)', lineHeight: 1.05, fontWeight: 700 }}>
            Where the world’s CO₂ comes from — and where it’s heading.
          </h1>
          {error ? (
            <InlineAlert variant="warning">{error}</InlineAlert>
          ) : (
            <p className="__s9cmpx-body1" style={{ margin: 0, color: 'var(--__s9cmpx-static-text-weak)' }} role="status">Loading the latest data…</p>
          )}
          <div>
            <Link to="/overview" className={ctaClass('primary')} style={{ textDecoration: 'none' }}>Explore the data</Link>
          </div>
        </section>
      )}
    </div>
  );
}
