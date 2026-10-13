import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, Select, DataTable, InlineAlert, KpiStat, Spinner, useReducedMotion } from 'design-system';
import { Link } from 'react-router-dom';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useSelectedCountry } from '../hooks/useCountrySelection';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import type { CountryCumulativeResponse, CountryProfileTableRow } from '../api/types';
import { resolveDivergingEndpointHex } from '../lib/resolveThemeColorHex';
import { useThemeColorHex } from '../hooks/useThemeColorHex';
import { fmtGt } from '../lib/cumulative';
import { StickyJumpLinks, useStickyRowReady } from '../components/StickyJumpLinks';

// The CO2 Emissions and CO2 per Capita line charts below pass no explicit `color`, so each
// fell back to SyChart's default single-series categorical color -- theme-specific
// `--__s9cmpx-chart-categorical-default-01`, which happens to be a near-white on Dark
// (#ecf0f6) but a yellow-green on Light (#D7E740) -- an unintended divergence (Claude Design
// theme-adherence review round 2): both themes render this chart on the SAME dark chart panel
// (`--__s9cmpx-chart-surface`), so there's no reason the line's own color should switch with
// the app's Light/Dark toggle the way a page's surrounding chrome does. Pinning both series to
// one fixed literal (rather than resolving a per-theme token, the pattern used everywhere else
// in this app) is deliberately the right tool here -- `SyChartSeries.color` exists specifically
// to override the theme-varying categorical default with "any CSS color" for exactly this case.
// Reused Dark's own existing near-white value rather than inventing a new one: manually
// verified contrast against both panel backgrounds (Light #061E28, Dark #121e35 -- see
// resolveThemeColorHex.ts's DIVERGING_MID_VAR comment for how the panel hexes differ per
// theme) comes out to 15.0:1 and 14.54:1, both comfortably AAA.
const SINGLE_LINE_COLOR = '#ecf0f6';

const COLUMNS: ColDef<CountryProfileTableRow>[] = [
  { field: 'year', headerName: 'Year' },
  { field: 'co2', headerName: 'CO₂ (MtCO₂)' },
  { field: 'co2_per_capita', headerName: 'CO₂ per Capita (t/person)' },
  { field: 'co2_yoy_pct_change', headerName: 'YoY % Change' },
  { field: 'ghg_intensity', headerName: 'GHG Intensity (kg CO₂e/$ GDP)' },
];

// Stable labels (SPEC.md §5.19) -- distinct from the ChartCards' own titles, which are always
// suffixed with the currently-selected country.
const JUMP_ITEMS: JumpLinkItem[] = [
  { id: 'emissions', label: 'Emissions', href: '#emissions' },
  // topSection (SPEC.md §5.20): stacked directly under "Emissions", close enough a neighbor
  // that scrolling it away while both are already visible would just hide the nav for no
  // benefit -- still scrolls normally once it's genuinely below the fold (e.g. mobile).
  { id: 'per-capita', label: 'Per Capita', href: '#per-capita', topSection: true },
  { id: 'yoy-change', label: 'YoY Change', href: '#yoy-change' },
  { id: 'key-stats', label: 'Key Statistics', href: '#key-stats' },
  { id: 'cumulative', label: 'Cumulative', href: '#cumulative' },
];

// Split out so the country-profile fetch only ever starts once the expanded country list
// (and its featured-default seed) are already known — avoiding a wasted initial fetch for
// an undefined country before GET /api/countries resolves.
function CountryProfileContent({ featured, expanded }: { featured: string[]; expanded: string[] }) {
  // URL-backed (?country=…, SPEC.md §5.25) so links can open a specific country's profile.
  const [country, setCountry] = useSelectedCountry(featured[0], expanded);
  const { data, error, loading } = useAsync(() => api.countryProfile(country), [country]);
  // Its own request, so a slow or failed cumulative fetch never blanks the sections above it (SPEC.md §5.28).
  const cumulative = useAsync(() => api.countryCumulative(country), [country]);
  const reduceMotion = useReducedMotion();
  // The deep-link jump also waits for the pinned row's first measurement: where it wraps, the offset is wrong until then.
  const { rowReady, onRowReady } = useStickyRowReady();
  useJumpToHashOnLoad(rowReady && Boolean(data), reduceMotion);
  // Resolved once per render rather than once per YoY data point (Copilot review, PR #157) --
  // the underlying computed style can't change mid-render, so mapping every value through
  // resolveDivergingEndpointHex() individually was N redundant DOM/getComputedStyle calls for
  // what's really just 2 distinct colors. Goes through useThemeColorHex (not a bare call)
  // because calling the resolver directly in a render body races the Bright/Dark toggle's
  // own commit -- see that hook's comment. Uses the same brown/teal diverging pair as
  // Overview's % Change chart and the Scenario Comparison treemap (not the separate literal
  // red/green sentiment tokens) so all three CO2-direction charts agree visually.
  const positiveColorHex = useThemeColorHex(() => resolveDivergingEndpointHex('positive'));
  const negativeColorHex = useThemeColorHex(() => resolveDivergingEndpointHex('negative'));

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 16px' }}>Country Profile</h1>
      <StickyJumpLinks onReady={onRowReady} items={JUMP_ITEMS} />

      <Select
        label={`Select a country (${expanded.length} available)`}
        options={expanded.map((c) => ({ value: c, label: c }))}
        value={country}
        onChange={setCountry}
      />

      {loading ? (
        <Spinner />
      ) : error ? (
        <InlineAlert variant="warning">{error}</InlineAlert>
      ) : data ? (
        <>
          {/* min(280px, 100%) — not a bare 280px floor — since a track that can never
              shrink below 280px still overflows a ~272px content area on the narrowest
              real phones (320px viewport, e.g. Galaxy S9+), even with auto-fit. */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16, margin: '16px 0' }}>
            <ChartCard id="emissions" title={`CO₂ Emissions — ${country}`} headingLevel={2} expandable>
              {(isExpanded) => (
                <SyChart height={isExpanded ? 560 : 280} xTitle="Year" yTitle="CO₂ (MtCO₂)" showLegend={false} ariaLabel={`Line chart of total CO₂ emissions for ${country} from ${data.years[0]} to ${data.years[data.years.length - 1]}`} series={[{ name: 'CO₂', x: data.years, y: data.co2, kind: 'line', color: SINGLE_LINE_COLOR }]} />
              )}
            </ChartCard>
            <ChartCard id="per-capita" title={`CO₂ per Capita — ${country}`} headingLevel={2} expandable>
              {(isExpanded) => (
                <SyChart height={isExpanded ? 560 : 280} xTitle="Year" yTitle="tCO₂/person" showLegend={false} ariaLabel={`Line chart of CO₂ emissions per capita for ${country} from ${data.years[0]} to ${data.years[data.years.length - 1]}`} series={[{ name: 'CO₂ per Capita', x: data.years, y: data.co2_per_capita, kind: 'line', color: SINGLE_LINE_COLOR }]} />
              )}
            </ChartCard>
          </div>

          <ChartCard id="yoy-change" title={`Year-on-Year CO₂ Change — ${country}`} headingLevel={2}>
            <SyChart
              height={280}
              xTitle="Year"
              yTitle="YoY % Change"
              showLegend={false}
              ariaLabel={`Bar chart of year-over-year percent change in CO₂ emissions for ${country}, colored on a diverging scale from a decrease (favorable) to an increase (unfavorable)`}
              series={[{
                name: 'YoY % Change',
                x: data.yoy_years,
                y: data.yoy_values,
                kind: 'bar',
                pointColors: data.yoy_values.map((v) => (v < 0 ? positiveColorHex : negativeColorHex)),
              }]}
            />
          </ChartCard>

          <div id="key-stats" style={{ marginTop: 24 }}>
            <h2 className="__s9cmpx-headline6">Key Statistics</h2>
            <DataTable columns={COLUMNS} rows={data.table} />
          </div>

          <div id="cumulative" style={{ marginTop: 24 }}>
            <h2 className="__s9cmpx-headline6">Cumulative contribution</h2>
            {cumulative.loading ? (
              <Spinner />
            ) : cumulative.error ? (
              <InlineAlert variant="warning">{cumulative.error}</InlineAlert>
            ) : cumulative.data ? (
              <CumulativeSection country={country} data={cumulative.data} />
            ) : null}
          </div>
        </>
      ) : null}
    </div>
  );
}

function CumulativeSection({ country, data }: { country: string; data: CountryCumulativeResponse }) {
  const { latest } = data;
  const first = data.years[0];
  const lastYear = data.years[data.years.length - 1];
  const shareLabel = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1)}%`);
  const firstShare = data.share_of_world_cumulative[0];

  if (!latest) return <InlineAlert variant="warning">{`No cumulative CO₂ data for ${country}.`}</InlineAlert>;

  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: 16, margin: '12px 0' }}>
        <KpiStat card label={`Cumulative CO₂ since records began · ${latest.year}`} value={`${fmtGt(latest.cumulative_co2 / 1000)} GtCO₂`} delta="Fossil and cement" deltaDirection="neutral" />
        <KpiStat card label="Share of world total" value={shareLabel(latest.share_of_world_cumulative)} delta={firstShare == null ? undefined : `${shareLabel(firstShare)} in ${first}`} deltaDirection="neutral" />
        <KpiStat card label={`Rank by cumulative CO₂ · ${latest.year}`} value={`#${latest.rank}`} delta={`of ${latest.rank_of} countries`} deltaDirection="neutral" />
      </div>
      <ChartCard title={`Share of World CO₂ — ${country}`} headingLevel={3}>
        <p className="__s9cmpx-body4" style={{ margin: '0 0 8px', color: 'var(--__s9cmpx-static-text-weak)' }}>
          <strong>Purpose:</strong> Solid line: share of all CO₂ emitted so far. Dotted line: share of each year&rsquo;s emissions. When the dotted line is above the solid one, the country&rsquo;s share of the total is rising.
        </p>
        <SyChart
          height={280}
          xTitle="Year"
          yTitle="% of world"
          ariaLabel={`Line chart of ${country}'s share of the world's cumulative CO₂ and of each year's CO₂ emissions, ${first} to ${lastYear}`}
          series={[
            { name: 'Share of cumulative total', x: data.years, y: data.share_of_world_cumulative, kind: 'line', color: SINGLE_LINE_COLOR },
            { name: "Share of that year's emissions", x: data.years, y: data.share_of_world_annual, kind: 'line', color: SINGLE_LINE_COLOR, dashed: true },
          ]}
        />
        <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
          Fossil and cement CO₂ · OWID · counted from each country&rsquo;s first record, shown from {first}. Shares are of the World total, international aviation and shipping included, the same as in Climate Correlation, which also offers PRIMAP-hist.{' '}
          <Link to="/climate-correlation">Open in Climate Correlation</Link>
        </p>
      </ChartCard>
    </>
  );
}

export default function CountryProfilePage() {
  const countries = useCountries();

  if (countries.loading) return <Spinner />;
  if (countries.error) return <InlineAlert variant="warning">{countries.error}</InlineAlert>;
  if (!countries.data) return null;

  return <CountryProfileContent featured={countries.data.featured} expanded={countries.data.expanded} />;
}
