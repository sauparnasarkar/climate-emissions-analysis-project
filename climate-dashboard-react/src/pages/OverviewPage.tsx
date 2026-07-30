import { useState, type CSSProperties } from 'react';
import { KpiStat, ChartCard, SyChart, MultiSelect, Button, InlineAlert, Spinner, Icon } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { useCountUp } from '../hooks/useCountUp';
import { MAX_SELECTED_COUNTRIES, POSITIVE_COLOR, NEGATIVE_COLOR } from '../constants';
import type { OverviewTierMetrics } from '../api/types';

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
function CountUpText({ value, format }: { value: number; format: (n: number) => string }) {
  const animated = useCountUp(value);
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
}

function tierRow(title: string, icon: TierIcon, tier: OverviewTierMetrics): TierRow {
  return {
    tier: title,
    icon,
    countries: tier.countries_count,
    co2Total: tier.latest_co2_total,
    pctChange: tier.pct_change_since_1990,
  };
}

// Three stacked mini cards (one per tier) instead of a 4-column table — reads better at
// ~33% width than a table whose columns would otherwise be squeezed illegibly narrow.
// Each card shows the same three metrics vertically; the wrapper class carries this
// component's one-off responsive/layout CSS the same way overview-tier-table (its
// table-based predecessor) scoped its own header-background rule.
function TierSummaryPanel({ rows, year }: { rows: TierRow[]; year: number }) {
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
            <span className="__s9cmpx-headline4"><CountUpText value={row.countries} format={(n) => Math.round(n).toLocaleString()} /></span>
          </div>
          <div className="overview-tier-panel__metric">
            <span className="__s9cmpx-body2">{`CO₂ (${year})`}</span>
            <span className="__s9cmpx-headline4"><CountUpText value={row.co2Total} format={(n) => `${n.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`} /></span>
          </div>
          <div className="overview-tier-panel__metric">
            <span className="__s9cmpx-body2">% Change since 1990</span>
            <span className="__s9cmpx-headline4" style={{ color: row.pctChange >= 0 ? NEGATIVE_COLOR : POSITIVE_COLOR }}>
              <CountUpText value={row.pctChange} format={(n) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`} />
            </span>
          </div>
        </div>
      ))}
    </div>
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

  // useAsync preserves the previous `data` while a refetch is in flight (only `loading`
  // flips), so only block on a spinner before anything has ever loaded — once `data`
  // exists, keep the picker/last-good UI mounted across every selection change instead of
  // unmounting the whole page (and its MultiSelect) on every refetch.
  if (error) return <InlineAlert variant="warning">{error}</InlineAlert>;
  if (!data) return loading ? <Spinner /> : null;

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
        <ChartCard title={`CO₂ Emissions by Country (${data.all_countries.latest_year})`} headingLevel={2}>
          <SyChart
            showLegend={false}
            ariaLabel={`World map choropleth of CO₂ emissions by country in ${data.all_countries.latest_year}, log-scaled color from light (lowest) to deep red (highest)`}
            series={[{
              name: 'CO₂',
              x: [],
              y: [],
              kind: 'choropleth',
              locations: data.world_map.map((p) => p.iso_code ?? ''),
              zLog: true,
              colorValues: data.world_map.map((p) => p.value),
              colorScale: MAGNITUDE_SCALE,
              colorbarTitle: 'CO₂ (MtCO₂)',
              hoverUnit: 'MtCO₂',
            }]}
          />
        </ChartCard>

        <TierSummaryPanel
          year={data.all_countries.latest_year}
          rows={[
            tierRow('All Countries', 'grid', data.all_countries),
            tierRow('Expanded (Coverage + ≥100 Mt)', 'document', data.expanded_countries),
            ...(selected.length > 0 ? [tierRow('Selected', 'check', data.selected)] : []),
          ]}
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
              series={[{ name: 'CO₂', x: barSeries, y: barValues, kind: 'bar' }]}
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
