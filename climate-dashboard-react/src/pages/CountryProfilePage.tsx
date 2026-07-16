import { useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { ChartCard, SyChart, Select, DataTable, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { COUNTRIES } from '../constants';
import type { CountryProfileTableRow } from '../api/types';

const COLUMNS: ColDef<CountryProfileTableRow>[] = [
  { field: 'year', headerName: 'Year' },
  { field: 'co2', headerName: 'CO₂ (MtCO₂)' },
  { field: 'co2_per_capita', headerName: 'CO₂ per Capita (t/person)' },
  { field: 'co2_yoy_pct_change', headerName: 'YoY % Change' },
  { field: 'ghg_intensity', headerName: 'GHG Intensity (kg CO₂e/$ GDP)' },
];

export default function CountryProfilePage() {
  const [country, setCountry] = useState<string>(COUNTRIES[0]);
  const { data, error, loading } = useAsync(() => api.countryProfile(country), [country]);

  return (
    <div>
      <h1 className="sy-headline2" style={{ margin: '0 0 16px' }}>Country Profile</h1>

      <Select
        label="Select a country"
        options={COUNTRIES.map((c) => ({ value: c, label: c }))}
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
            <ChartCard title={`CO₂ Emissions — ${country}`}>
              <SyChart height={280} xTitle="Year" yTitle="CO₂ (MtCO₂)" showLegend={false} ariaLabel={`Line chart of total CO₂ emissions for ${country} from ${data.years[0]} to ${data.years[data.years.length - 1]}`} series={[{ name: 'CO₂', x: data.years, y: data.co2, kind: 'line' }]} />
            </ChartCard>
            <ChartCard title={`CO₂ per Capita — ${country}`}>
              <SyChart height={280} xTitle="Year" yTitle="tCO₂/person" showLegend={false} ariaLabel={`Line chart of CO₂ emissions per capita for ${country} from ${data.years[0]} to ${data.years[data.years.length - 1]}`} series={[{ name: 'CO₂ per Capita', x: data.years, y: data.co2_per_capita, kind: 'line' }]} />
            </ChartCard>
          </div>

          <ChartCard title={`Year-on-Year CO₂ Change — ${country}`}>
            <SyChart
              height={280}
              xTitle="Year"
              yTitle="YoY % Change"
              showLegend={false}
              ariaLabel={`Bar chart of year-over-year percent change in CO₂ emissions for ${country}, colored red for decreases and blue for increases`}
              series={[{
                name: 'YoY % Change',
                x: data.yoy_years,
                y: data.yoy_values,
                kind: 'bar',
                pointColors: data.yoy_values.map((v) => (v < 0 ? '#dc2626' : '#4a90d9')),
              }]}
            />
          </ChartCard>

          <div style={{ marginTop: 24 }}>
            <h2 className="sy-headline6">Key Statistics</h2>
            <DataTable columns={COLUMNS} rows={data.table} />
          </div>
        </>
      ) : null}
    </div>
  );
}
