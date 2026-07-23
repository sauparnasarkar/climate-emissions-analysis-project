import { useMemo, useState } from 'react';
import type { ColDef } from 'ag-grid-community';
import { Button, MultiSelect, RangeSlider, DataTable, InlineAlert, Spinner } from 'design-system';
import { api } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import type { ExplorerMetaResponse } from '../api/types';

const DEFAULT_COLUMNS = ['country', 'year', 'co2', 'co2_per_capita', 'population', 'gdp', 'total_ghg'];
const PAGE_SIZE = 50;

function humanize(field: string): string {
  return field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// Split out so the data/summary fetches only ever start once `meta` (and the default
// column selection / year range derived from it) are already known — avoiding a wasted
// initial fetch of all 79 columns before the intended default subset is set.
function DataExplorerContent({ meta }: { meta: ExplorerMetaResponse }) {
  const [countries, setCountries] = useState<string[]>([]);
  const [yearMin, setYearMin] = useState(meta.year_min);
  const [yearMax, setYearMax] = useState(meta.year_max);
  const [columns, setColumns] = useState<string[]>(DEFAULT_COLUMNS.filter((c) => meta.columns.includes(c)));
  const [page, setPage] = useState(1);

  const data = useAsync(
    () => api.explorerData(countries, yearMin, yearMax, columns, page, PAGE_SIZE),
    [countries, yearMin, yearMax, columns, page],
  );
  const summary = useAsync(
    () => api.explorerSummary(countries, yearMin, yearMax, columns),
    [countries, yearMin, yearMax, columns],
  );

  const totalPages = data.data ? Math.max(1, Math.ceil(data.data.total_rows / PAGE_SIZE)) : 1;

  // AG Grid treats a new `columnDefs` array reference as a real column-model change and
  // fully rebuilds the grid's column/header state — since this page's data (and its own
  // fresh `.map()` result) refetches on every filter tweak, an unmemoized array here forces
  // a full column rebuild on every keystroke/drag update instead of only when the actual
  // set of column names changes.
  const dataColumnsKey = (data.data?.columns ?? []).join(',');
  const dataColumns: ColDef[] = useMemo(
    () => (data.data?.columns ?? []).map((c) => ({ field: c, headerName: humanize(c) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dataColumnsKey],
  );
  const summaryColumnsKey = (summary.data?.columns ?? []).join(',');
  const summaryColumns: ColDef[] = useMemo(
    () =>
      (summary.data?.columns ?? []).map((c) => ({
        field: c,
        headerName: c === 'statistic' ? 'Statistic' : humanize(c),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [summaryColumnsKey],
  );
  const downloadUrl = api.explorerDownloadUrl(countries, yearMin, yearMax, columns);

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <MultiSelect
          label="Countries (leave empty to show all)"
          options={meta.countries.map((c) => ({ value: c, label: c }))}
          value={countries}
          onChange={(next) => {
            setCountries(next);
            setPage(1);
          }}
        />
        <RangeSlider
          label="Year range"
          min={meta.year_min}
          max={meta.year_max}
          value={[yearMin, yearMax]}
          thumbLabels={['From year', 'To year']}
          onChange={([lo, hi]) => {
            setYearMin(lo);
            setYearMax(hi);
            setPage(1);
          }}
        />
        <MultiSelect
          label="Columns"
          options={meta.columns.map((c) => ({ value: c, label: humanize(c) }))}
          value={columns}
          onChange={(next) => {
            setColumns(next);
            setPage(1);
          }}
        />
      </div>

      <h2 className="__s9cmpx-headline6">Dataset Preview</h2>
      {columns.length === 0 ? (
        <InlineAlert variant="default">Select at least one column to preview the data.</InlineAlert>
      ) : data.loading ? (
        <Spinner />
      ) : data.error ? (
        <InlineAlert variant="warning">{data.error}</InlineAlert>
      ) : data.data ? (
        <>
          <p className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)', margin: '4px 0 8px' }}>
            {data.data.total_rows.toLocaleString()} rows · page {page} of {totalPages}
          </p>
          <DataTable columns={dataColumns} rows={data.data.rows} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
            <Button variant="secondary" size="s" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Previous
            </Button>
            <Button
              variant="secondary"
              size="s"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Next
            </Button>
            <a
              href={downloadUrl}
              download
              className="__s9cmpx-button __s9cmpx-button--secondary __s9cmpx-button--s"
              style={{ marginLeft: 'auto' }}
            >
              Download filtered data as CSV
            </a>
          </div>
        </>
      ) : null}

      <h2 className="__s9cmpx-headline6" style={{ marginTop: 24 }}>Summary Statistics</h2>
      {summary.loading ? (
        <Spinner />
      ) : summary.error ? (
        <InlineAlert variant="warning">{summary.error}</InlineAlert>
      ) : summary.data ? (
        <DataTable columns={summaryColumns} rows={summary.data.rows} />
      ) : null}
    </div>
  );
}

export default function DataExplorerPage() {
  const meta = useAsync(() => api.explorerMeta(), []);

  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Data Explorer</h1>
      <p className="__s9cmpx-body3-short" style={{ marginBottom: 16, color: 'var(--__s9cmpx-static-text-weak)' }}>
        Browse the full underlying dataset behind this dashboard: every sovereign country
        (regional and income-group aggregates like &quot;World&quot; or &quot;European
        Union&quot; excluded), from 1990 onward — the raw and derived OWID columns, not just
        the 10 focus countries or the reduced feature set used elsewhere in this app.
      </p>

      {meta.loading ? <Spinner /> : meta.error ? <InlineAlert variant="warning">{meta.error}</InlineAlert> : meta.data ? (
        <DataExplorerContent meta={meta.data} />
      ) : null}
    </div>
  );
}
