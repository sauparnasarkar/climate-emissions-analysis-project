import { useMemo, useState } from 'react';
import { ChartCard, InlineAlert, MultiSelect, SyChart } from 'design-system';
import { api } from '../../api/client';
import { useAsync } from '../../hooks/useAsync';
import { NO_COUNTRY_ATTRIBUTION } from '../../lib/climateCopy';
import type { YearValue } from '../../lib/climateSignal';
import { COUNTRY_VIEW_ANCHOR, COUNTRY_VIEW_MAX, buildCountryLines, defaultCountries } from '../../lib/countryView';
import { fmtShare } from '../../lib/shareBars';
import { BaselineChip } from '../climate/BaselineChip';
import { PurposeLine } from '../climate/PurposeLine';

const TEMP_COLOR = '#EA5B62';
const SHARE_FROM = 1850;

/**
 * The country view (requirements §1.3.4; ENHANCEMENTS.md decision 66): each selected country's share of cumulative CO₂ over time, beside the global
 * temperature anomaly. Shown together for context only: no country series is regressed against the global temperature series, and no warming is
 * attributed to a country. The share's denominator is the national sum (international aviation and shipping excluded), so it differs by design
 * from the World series behind the headline relationship.
 */
export function CountryView({ temperature, mean5y }: { temperature: YearValue[]; mean5y: YearValue[] | null }) {
  // Every country at the latest year, ranked: the picker's pool, and the largest five are where it starts.
  const snapshot = useAsync(async () => api.correlationCountryShare({ allCountries: true }), []);
  const [chosen, setChosen] = useState<string[] | null>(null);
  const defaults = useMemo(() => defaultCountries(snapshot.data), [snapshot.data]);
  const selected = chosen ?? defaults;
  const key = selected.join(',');
  const options = useMemo(() => (snapshot.data?.rows ?? []).map((r) => ({ value: r.country, label: r.name })), [snapshot.data]);

  const query = useAsync(
    async () => (selected.length ? api.correlationCountryShare({ countries: selected, startYear: SHARE_FROM }) : null),
    [key],
  );
  // useAsync keeps the previous response while a refetch runs; showing it under a new selection would present old lines as the new ones.
  const lines = useMemo(() => (query.loading ? null : buildCountryLines(query.data)), [query.data, query.loading]);

  const body = (() => {
    if (snapshot.error && !snapshot.data) return <InlineAlert variant="warning">{snapshot.error}</InlineAlert>;
    // /country-share answers a year outside its coverage with 200 and no rows plus a note: say so, rather than showing an empty picker and a bare prompt.
    if (snapshot.data && snapshot.data.rows.length === 0) {
      const [lo, hi] = snapshot.data.coverage ?? [];
      return (
        <InlineAlert variant="warning">
          {`No country shares are available${snapshot.data.year != null ? ` for ${snapshot.data.year}` : ''}.${lo != null && hi != null ? ` Coverage is ${lo}–${hi}.` : ''}${snapshot.data.notes.length ? ` ${snapshot.data.notes.join(' ')}` : ''}`}
        </InlineAlert>
      );
    }
    if (selected.length === 0) return <p className="__s9cmpx-body3" style={{ margin: 0 }}>Choose countries to compare their shares.</p>;
    if (query.error) return <InlineAlert variant="warning">{query.error}</InlineAlert>;
    if (!lines) return <p className="__s9cmpx-body3" style={{ margin: 0 }}>{query.loading ? 'Loading…' : 'No share data is available for these countries.'}</p>;
    const lastYear = Math.max(...lines.lines.flatMap((l) => l.points.map((p) => p.year)));
    const firstYear = Math.min(...lines.lines.flatMap((l) => l.points.map((p) => p.year)));
    return (
      <>
        {lines.missing.length > 0 && (
          <InlineAlert variant="warning">
            No data for {lines.missing.map((m) => m.name).join(', ')}; {lines.missing.length === 1 ? 'it is' : 'they are'} left out.{lines.notes.length ? ` ${lines.notes.join(' ')}` : ''}
          </InlineAlert>
        )}
        <SyChart
          height={300}
          yTitle="Share of cumulative CO₂ (%)"
          ariaLabel={`Line chart of each selected country's share of cumulative CO₂, ${firstYear} to ${lastYear}. In ${lastYear}: ${lines.lines.map((l) => `${l.name} ${fmtShare(l.points[l.points.length - 1].share)}`).join(', ')}.`}
          series={lines.lines.map((l) => ({ name: l.name, x: l.points.map((p) => p.year), y: l.points.map((p) => p.share), kind: 'line' as const, color: l.color, showMarkers: false }))}
        />
        <table style={{ width: '100%', maxWidth: 420, marginTop: 8, borderCollapse: 'collapse', fontVariantNumeric: 'tabular-nums' }}>
          <caption className="__s9cmpx-body4" style={{ textAlign: 'left', color: 'var(--__s9cmpx-static-text-weak)', paddingBottom: 4 }}>Share of cumulative CO₂, {lastYear}</caption>
          <tbody>
            {lines.lines.map((l) => (
              <tr key={l.code} className="__s9cmpx-body3">
                <th scope="row" style={{ textAlign: 'left', fontWeight: 400 }}>
                  <span aria-hidden style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: l.color, marginRight: 8 }} />
                  {l.name}
                </th>
                <td style={{ textAlign: 'right' }}>{fmtShare(l.points[l.points.length - 1].share)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 8 }}>
          <BaselineChip baseline={`cumulative${lines.cumulativeFrom != null ? ` since ${lines.cumulativeFrom}` : ''}`} source="national sum, bunkers excluded · OWID" />
        </div>
      </>
    );
  })();

  const tempFirst = temperature[0]?.year;
  const tempLast = temperature[temperature.length - 1]?.year;
  return (
    <section id={COUNTRY_VIEW_ANCHOR} aria-labelledby="country-view-heading" style={{ marginBottom: 24 }}>
      <style>{'@media (max-width: 1100px) { .module-country-grid { grid-template-columns: 1fr !important; } }'}</style>
      <h2 id="country-view-heading" className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>Country view</h2>
      <InlineAlert variant="default">{NO_COUNTRY_ATTRIBUTION}</InlineAlert>
      <div className="module-country-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 16, alignItems: 'start', marginTop: 12 }}>
        <ChartCard title="Share of cumulative CO₂ by country" headingLevel={3}>
          <PurposeLine>show how each country&apos;s part of all CO₂ emitted so far has changed. Contribution to emissions, not to warming.</PurposeLine>
          {options.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <MultiSelect
                label={`Countries (up to ${COUNTRY_VIEW_MAX})`}
                options={options}
                value={selected}
                onChange={(v) => setChosen(v)}
                maxSelected={COUNTRY_VIEW_MAX}
              />
            </div>
          )}
          {body}
        </ChartCard>
        {tempFirst != null && (
          <ChartCard title="Global temperature anomaly" headingLevel={3}>
            <PurposeLine>show the global warming record the shares are set beside: one global line, not a country series.</PurposeLine>
            <SyChart
              height={300}
              yTitle="°C above 1850–1900"
              ariaLabel={`Line chart of the global temperature anomaly in °C above the 1850 to 1900 mean, ${tempFirst} to ${tempLast}${mean5y?.length ? ', with its 5-year mean' : ''}.`}
              series={[
                { name: 'Annual', x: temperature.map((p) => p.year), y: temperature.map((p) => p.value), kind: 'line', color: 'rgba(234, 91, 98, 0.45)', showMarkers: false },
                ...(mean5y?.length ? [{ name: '5-year mean', x: mean5y.map((p) => p.year), y: mean5y.map((p) => p.value), kind: 'line' as const, color: TEMP_COLOR, showMarkers: false }] : []),
              ]}
            />
            <div style={{ marginTop: 8 }}>
              <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
            </div>
          </ChartCard>
        )}
      </div>
    </section>
  );
}
