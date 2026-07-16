import { useState } from 'react';
import { ChartCard, SyChart, MultiSelect, Select, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { COUNTRIES, GAS_COLUMNS } from '../constants';

const GAS_OPTIONS = Object.entries(GAS_COLUMNS).map(([value, label]) => ({ value, label }));

export default function HistoricalTrendsPage() {
  const [selectedCountries, setSelectedCountries] = useState<string[]>(COUNTRIES.slice(0, 5) as string[]);
  const [gas, setGas] = useState('co2');

  const timeseries = useAsync(
    () => api.historicalTimeseries(selectedCountries, gas),
    [selectedCountries.join(','), gas],
  );
  const composition = useAsync(() => api.historicalDecadeComposition(), []);

  return (
    <div>
      <h1 className="sy-headline2" style={{ margin: '0 0 16px' }}>Historical Emissions Trends</h1>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <MultiSelect
          label="Select countries"
          options={COUNTRIES.map((c) => ({ value: c, label: c }))}
          value={selectedCountries}
          onChange={setSelectedCountries}
        />
        <Select label="Emissions metric" options={GAS_OPTIONS} value={gas} onChange={setGas} />
      </div>

      <h2 className="sy-headline6">{GAS_COLUMNS[gas]} Emissions Over Time</h2>
      {selectedCountries.length === 0 ? (
        <InlineAlert variant="warning">Select at least one country.</InlineAlert>
      ) : timeseries.loading ? (
        <Spinner />
      ) : timeseries.error ? (
        <InlineAlert variant="warning">{timeseries.error}</InlineAlert>
      ) : (
        <ChartCard title={`${GAS_COLUMNS[gas]} Emissions by Country`}>
          <SyChart
            height={320}
            xTitle="Year"
            yTitle={`${GAS_COLUMNS[gas]} (MtCO₂e)`}
            ariaLabel={`Line chart of ${GAS_COLUMNS[gas]} emissions over time for ${selectedCountries.join(', ')}`}
            series={(timeseries.data?.series ?? []).map((s) => ({ name: s.name, x: s.years, y: s.values, kind: 'line' as const }))}
          />
        </ChartCard>
      )}

      <div style={{ marginTop: 24 }}>
        <h2 className="sy-headline6">GHG Share by Gas Type per Decade</h2>
        {composition.loading ? (
          <Spinner />
        ) : composition.error ? (
          <InlineAlert variant="warning">{composition.error}</InlineAlert>
        ) : (
          <ChartCard title="GHG Composition by Decade — 10 Countries (% share)">
            <SyChart
              height={320}
              barmode="stack"
              xTitle="Decade"
              yTitle="Share (%)"
              ariaLabel="Stacked bar chart of greenhouse gas composition by decade across the 10 focus countries, showing CO2, methane, and nitrous oxide share of total emissions"
              series={(composition.data?.series ?? []).map((s) => ({
                name: s.gas_label,
                x: composition.data!.decades,
                y: s.share,
                kind: 'bar' as const,
              }))}
            />
          </ChartCard>
        )}
      </div>
    </div>
  );
}
