import { useState } from 'react';
import { KpiStat, ChartCard, SyChart, MultiSelect, Button, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { MAX_SELECTED_COUNTRIES } from '../constants';
import type { OverviewTierMetrics } from '../api/types';

function TierKpiRow({ title, tier }: { title: string; tier: OverviewTierMetrics }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <h2 className="__s9cmpx-headline6" style={{ margin: '0 0 8px' }}>{title}</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16 }}>
        <KpiStat card label={`CO₂ (${tier.latest_year})`} value={`${tier.latest_co2_total.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`} />
        <KpiStat
          card
          label="% Change since 1990"
          value={`${tier.pct_change_since_1990 >= 0 ? '+' : ''}${tier.pct_change_since_1990.toFixed(1)}%`}
          deltaDirection={tier.pct_change_since_1990 >= 0 ? 'up' : 'down'}
        />
        <KpiStat card label="Countries" value={tier.countries_count} />
      </div>
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
      <p className="__s9cmpx-body3-short" style={{ margin: '4px 0 16px', color: 'var(--__s9cmpx-static-text-weak)' }}>
        An end-to-end analysis of greenhouse gas emissions for {data.expanded_countries.countries_count} major countries using the OWID CO₂ dataset,
        regression models, and ETS(A,Ad,N) forecasting.
      </p>

      <TierKpiRow title="All Countries" tier={data.all_countries} />
      <TierKpiRow title="Expanded (Coverage + ≥100 Mt)" tier={data.expanded_countries} />

      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 12 }}>
        <MultiSelect
          label={`Select countries (up to ${MAX_SELECTED_COUNTRIES}/${expanded.length})`}
          options={expanded.map((c) => ({ value: c, label: c }))}
          value={selected}
          onChange={setSelected}
          maxSelected={MAX_SELECTED_COUNTRIES}
        />
        <Button variant="ghost-blue" size="s" onClick={() => setSelected(featured)}>Reset to default</Button>
      </div>
      <p className="__s9cmpx-label2" style={{ marginBottom: 16 }}>{data.selected_country_list.join('  |  ')}</p>

      {selected.length === 0 ? (
        <InlineAlert variant="warning">Select at least one country.</InlineAlert>
      ) : (
        <>
          <TierKpiRow title="Selected" tier={data.selected} />

          <ChartCard title={`CO₂ Emissions by Country (${data.selected.latest_year})`}>
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
                value={`${(data.fastest_growth.pct_change ?? 0) >= 0 ? '+' : ''}${(data.fastest_growth.pct_change ?? 0).toFixed(1)}%`}
                delta={`${(data.fastest_growth.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.fastest_growth.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="up"
              />
              <KpiStat
                card
                label={`Largest Reduction — ${data.largest_reduction.country}`}
                value={`${(data.largest_reduction.pct_change ?? 0) >= 0 ? '+' : ''}${(data.largest_reduction.pct_change ?? 0).toFixed(1)}%`}
                delta={`${(data.largest_reduction.absolute_change ?? 0) >= 0 ? '+' : ''}${(data.largest_reduction.absolute_change ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`}
                deltaDirection="down"
              />
            </div>

            <ChartCard title={`CO₂ % Change by Country, 1990–${data.selected.latest_year}`}>
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
