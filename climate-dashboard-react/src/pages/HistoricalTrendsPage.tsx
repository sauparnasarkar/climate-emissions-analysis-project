import { useState } from 'react';
import { ChartCard, SyChart, MultiSelect, Select, Button, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { useCountries } from '../hooks/useCountries';
import { GAS_COLUMNS, MAX_SELECTED_COUNTRIES } from '../constants';

const GAS_OPTIONS = Object.entries(GAS_COLUMNS).map(([value, label]) => ({ value, label }));

// Split out so the timeseries fetch only ever starts once the expanded country list (and
// its featured-default seed) are already known — avoiding a wasted initial fetch before
// GET /api/countries resolves.
function HistoricalTrendsContent({ featured, expanded }: { featured: string[]; expanded: string[] }) {
  // Defaults to the full 10 featured countries, matching Overview's Selected tier default
  // (previously just the first 5 here — inconsistent with the rest of the app).
  const [selectedCountries, setSelectedCountries] = useState<string[]>(featured);
  const [gas, setGas] = useState('co2');

  const timeseries = useAsync(
    () => api.historicalTimeseries(selectedCountries, gas),
    [selectedCountries.join(','), gas],
  );
  const composition = useAsync(
    () => api.historicalDecadeComposition(selectedCountries),
    [selectedCountries.join(',')],
  );

  // One concrete annotation instance, not a systematic framework -- placed at the highest
  // 2020 value across the selected series so the label sits near the line it's calling out.
  const year2020Values = (timeseries.data?.series ?? []).flatMap((s) => {
    const idx = s.years.indexOf(2020);
    return idx >= 0 && s.values[idx] != null ? [s.values[idx] as number] : [];
  });
  const lockdownAnnotation =
    year2020Values.length > 0 ? [{ x: 2020, y: Math.max(...year2020Values), text: 'Global lockdowns' }] : undefined;

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 16px' }}>Historical Emissions Trends</h1>

      <div className="country-picker-row" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: 12, marginBottom: 16 }}>
        <MultiSelect
          label={`Select countries (up to ${MAX_SELECTED_COUNTRIES}/${expanded.length})`}
          options={expanded.map((c) => ({ value: c, label: c }))}
          value={selectedCountries}
          onChange={setSelectedCountries}
          maxSelected={MAX_SELECTED_COUNTRIES}
        />
        <Button variant="ghost-blue" onClick={() => setSelectedCountries(featured)}>Reset to default</Button>
        <Select label="Emissions metric" options={GAS_OPTIONS} value={gas} onChange={setGas} />
      </div>

      <h2 className="__s9cmpx-headline6">{GAS_COLUMNS[gas]} Emissions Over Time</h2>
      {selectedCountries.length === 0 ? (
        <InlineAlert variant="warning">Select at least one country.</InlineAlert>
      ) : timeseries.loading ? (
        <Spinner />
      ) : timeseries.error ? (
        <InlineAlert variant="warning">{timeseries.error}</InlineAlert>
      ) : (
        <ChartCard title={`${GAS_COLUMNS[gas]} Emissions by Country`} headingLevel={3}>
          <SyChart
            height={320}
            xTitle="Year"
            yTitle={`${GAS_COLUMNS[gas]} (MtCO₂e)`}
            ariaLabel={`Line chart of ${GAS_COLUMNS[gas]} emissions over time for ${selectedCountries.join(', ')}`}
            annotations={lockdownAnnotation}
            series={(timeseries.data?.series ?? []).map((s) => ({ name: s.name, x: s.years, y: s.values, kind: 'line' as const }))}
          />
        </ChartCard>
      )}

      <div style={{ marginTop: 24 }}>
        <h2 className="__s9cmpx-headline6">GHG Share by Gas Type per Decade</h2>
        {selectedCountries.length === 0 ? (
          <InlineAlert variant="warning">Select at least one country.</InlineAlert>
        ) : composition.loading ? (
          <Spinner />
        ) : composition.error ? (
          <InlineAlert variant="warning">{composition.error}</InlineAlert>
        ) : (
          <ChartCard title={`GHG Composition by Decade — ${selectedCountries.length} Countries (% share)`} headingLevel={3}>
            <SyChart
              height={320}
              barmode="stack"
              xTitle="Decade"
              yTitle="Share (%)"
              ariaLabel={`Stacked bar chart of greenhouse gas composition by decade across ${selectedCountries.length} analyzed countries, showing CO2, methane, and nitrous oxide share of total emissions`}
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

export default function HistoricalTrendsPage() {
  const countries = useCountries();

  if (countries.loading) return <Spinner />;
  if (countries.error) return <InlineAlert variant="warning">{countries.error}</InlineAlert>;
  if (!countries.data) return null;

  return (
    <HistoricalTrendsContent
      featured={countries.data.featured}
      expanded={countries.data.expanded}
    />
  );
}
