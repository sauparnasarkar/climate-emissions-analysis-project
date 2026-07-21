import { KpiStat, ChartCard, SyChart, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';

export default function OverviewPage() {
  const { data, error, loading } = useAsync(() => api.overview(), []);

  if (loading) return <Spinner />;
  if (error) return <InlineAlert variant="warning">{error}</InlineAlert>;
  if (!data) return null;

  const barSeries = data.latest_year_bar.map((c) => c.country);
  const barValues = data.latest_year_bar.map((c) => c.value ?? 0);

  const moverCountries = data.top_movers.map((m) => m.country);
  const moverPct = data.top_movers.map((m) => m.pct_change ?? 0);

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: 0 }}>GHG Emissions Trend Analysis and Forecasting</h1>
      <p className="__s9cmpx-body3-short" style={{ margin: '4px 0 16px', color: 'var(--__s9cmpx-static-text-weak)' }}>
        An end-to-end analysis of greenhouse gas emissions for 10 major countries using the OWID CO₂ dataset,
        regression models, and ETS(A,Ad,N) forecasting.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 16, marginBottom: 16 }}>
        <KpiStat card label={`10-Country CO₂ (${data.latest_year})`} value={`${data.latest_co2_total.toLocaleString(undefined, { maximumFractionDigits: 0 })} MtCO₂`} />
        <KpiStat
          card
          label="% Change since 1990"
          value={`${data.pct_change_since_1990 >= 0 ? '+' : ''}${data.pct_change_since_1990.toFixed(1)}%`}
          deltaDirection={data.pct_change_since_1990 >= 0 ? 'up' : 'down'}
        />
        <KpiStat card label="Countries Analysed" value={data.countries_count} />
      </div>

      <p className="__s9cmpx-label2" style={{ marginBottom: 16 }}>{data.focus_countries.join('  |  ')}</p>

      <ChartCard title={`CO₂ Emissions by Country (${data.latest_year})`}>
        <SyChart
          height={320}
          xTitle="Country"
          yTitle="CO₂ (MtCO₂)"
          showLegend={false}
          ariaLabel={`Bar chart of total CO₂ emissions in ${data.latest_year} for ${barSeries.length} countries, ranging from ${Math.min(...barValues).toLocaleString()} to ${Math.max(...barValues).toLocaleString()} MtCO₂`}
          series={[{ name: 'CO₂', x: barSeries, y: barValues, kind: 'bar' }]}
        />
      </ChartCard>

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">Top Movers Since 1990 (10 Focus Countries)</h2>
        <p className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
          Fastest growth and largest reduction in CO₂ emissions, 1990 → {data.latest_year}, among the 10 focus countries.
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

        <ChartCard title={`CO₂ % Change by Country, 1990–${data.latest_year}`}>
          <SyChart
            height={320}
            xTitle="Country"
            yTitle={`% Change in CO₂ (1990→${data.latest_year})`}
            showLegend={false}
            ariaLabel={`Bar chart of percent change in CO₂ emissions from 1990 to ${data.latest_year} for ${moverCountries.length} countries, colored on a gradient from green (decrease) to crimson (increase)`}
            series={[{
              name: '% Change',
              x: moverCountries,
              y: moverPct,
              kind: 'bar',
              colorValues: moverPct,
              colorbarTitle: `% Change in CO₂ (1990→${data.latest_year})`,
            }]}
          />
        </ChartCard>
      </div>
    </div>
  );
}
