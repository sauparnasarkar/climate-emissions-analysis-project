import { useMemo, useState } from 'react';
import { Button, ChartCard, InlineAlert, SegmentedControl, useReducedMotion } from 'design-system';
import { api } from '../../api/client';
import { useAsync } from '../../hooks/useAsync';
import { useShareReplay } from '../../hooks/useShareReplay';
import { SHARE_MEASURES, SHARE_START_YEAR, SHARE_STEP_MS, buildShareFrames, fmtShare, segmentLabel, type ShareCountry, type ShareMeasureId } from '../../lib/shareBars';
import { BaselineChip } from '../climate/BaselineChip';
import { PurposeLine } from '../climate/PurposeLine';
import { YearBadge } from './YearBadge';

export const SHARE_ANCHOR = 'share';

const REST_COLOR = 'var(--__s9cmpx-static-divider-standard, #BDD3DB)';
const SEGMENT_TEXT = '#071C24';
// Rest of world is a theme-neutral surface, so its label follows the theme's text colour rather than the fixed dark text the bright country colours use.
const REST_TEXT = 'var(--__s9cmpx-static-text-standard)';

export interface BarProps {
  title: string;
  subtitle: string;
  order: ShareCountry[];
  values: number[];
  /** The remainder segment (Rest of world); omit for a bar whose segments are the whole, e.g. the four gases */
  rest?: number;
  tween: boolean;
}

/** One 100% stacked bar. Segment widths are flex-grow so they tween; the legend table below is the readable, accessible form of the same numbers. */
export function ShareBar({ title, subtitle, order, values, rest, tween }: BarProps) {
  const summary = order.map((c, i) => `${c.name} ${fmtShare(values[i])}`).concat(rest === undefined ? [] : [`Rest of world ${fmtShare(rest)}`]).join(', ');
  const segment = (key: string, color: string, pct: number, text: string, textColor: string = SEGMENT_TEXT) => (
    <div
      key={key}
      style={{
        flex: `${Math.max(pct, 0)} 1 0`,
        minWidth: 0,
        background: color,
        color: textColor,
        fontSize: 12,
        fontWeight: 600,
        lineHeight: '44px',
        padding: pct >= 3 ? '0 6px' : 0,
        overflow: 'hidden',
        whiteSpace: 'nowrap',
        borderRadius: 4,
        transition: tween ? `flex-grow ${SHARE_STEP_MS}ms linear` : 'none',
      }}
    >
      <span className="share-seg-label">{text}</span>
    </div>
  );
  return (
    <div className="share-bar-row" style={{ display: 'grid', gridTemplateColumns: 'minmax(96px, 150px) minmax(0, 1fr)', gap: 12, alignItems: 'center' }}>
      <div>
        <div className="__s9cmpx-label3">{title}</div>
        <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{subtitle}</div>
      </div>
      <div role="img" aria-label={`${title}: ${summary}`} style={{ display: 'flex', gap: 2, height: 44 }}>
        {order.map((c, i) => segment(c.code, c.color, values[i], segmentLabel(c.code, values[i])))}
        {rest !== undefined && segment('rest', REST_COLOR, rest, segmentLabel('RoW', rest), REST_TEXT)}
      </div>
    </div>
  );
}

/**
 * Who emitted the stock, and who emits now (requirements §2.2; ENHANCEMENTS.md decision 63): two 100% stacked bars for the selected
 * countries -- their share of everything emitted since the cumulative start (the stock) and of one year's emissions (the flow) -- that play
 * 1970 → the page year. It shows the page year; "Replay" animates 1970 → that year (temporarily, changing nothing else on the page) and returns to it.
 * Shares describe contribution to emissions only; no warming is attributed to a country.
 */
export function ShareSection({ countries, year, pagePlaying }: { countries: string[]; year: number; pagePlaying: boolean }) {
  const [measureId, setMeasureId] = useState<ShareMeasureId>('owid_co2');
  const measure = SHARE_MEASURES.find((m) => m.id === measureId) ?? SHARE_MEASURES[0];
  const reduceMotion = useReducedMotion();
  const key = countries.join(',');
  const query = useAsync(
    async () => (countries.length ? api.correlationCountryShare({ source: measure.source, gasScope: measure.gasScope, countries, startYear: SHARE_START_YEAR }) : null),
    [measureId, key],
  );
  // useAsync keeps the previous response while a refetch is in flight; showing it under the newly chosen measure/selection would present the old data
  // as the new, so frames exist only for a settled response.
  const frames = useMemo(() => (query.loading ? null : buildShareFrames(query.data)), [query.data, query.loading]);
  const first = frames?.years[0] ?? SHARE_START_YEAR;
  const lastYear = frames?.years[frames.years.length - 1] ?? SHARE_START_YEAR;
  // The page year decides what is shown; a replay borrows the screen from 1970 up to it, then hands it back. It ends early when the page year
  // moves or the page's own Play starts.
  const { replayYear, replaying, start, stop } = useShareReplay(first, year, pagePlaying);
  const shown = Math.min(Math.max(replayYear ?? year, first), lastYear);
  const yi = frames ? Math.max(0, frames.years.indexOf(shown)) : 0;

  const body = (() => {
    if (countries.length === 0) return <p className="__s9cmpx-body3" style={{ margin: 0 }}>Select countries in the picker below to compare their shares.</p>;
    if (query.error) return <InlineAlert variant="warning">{query.error}</InlineAlert>;
    if (!frames) {
      const why = query.data?.notes?.length ? ` ${query.data.notes.join(' ')}` : '';
      return <p className="__s9cmpx-body3" style={{ margin: 0 }}>{query.loading ? 'Loading…' : `No share data is available for these countries in this measure.${why}`}</p>;
    }
    const { order } = frames;
    const stock = frames.stock[yi];
    const flow = frames.flow ? frames.flow[yi] : null;
    const sum = (row: number[]) => row.reduce((a, b) => a + b, 0);
    return (
      <>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, marginBottom: 12 }}>
          <Button variant="ghost-blue" onClick={replaying ? stop : start} disabled={!replaying && year <= first}>
            {replaying ? '■ Stop replay' : `▶ Replay ${first} → ${year}`}
          </Button>
          {replaying && (
            <div aria-hidden style={{ flex: '1 1 80px', height: 4, borderRadius: 2, background: 'var(--__s9cmpx-static-divider-weak)', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${year > first ? ((shown - first) / (year - first)) * 100 : 100}%`, background: 'var(--__s9cmpx-static-text-weak)' }} />
            </div>
          )}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span className="__s9cmpx-body4" style={{ color: replaying ? 'var(--__s9cmpx-static-text-warning, #8A5A00)' : 'var(--__s9cmpx-static-text-weak)' }}>{replaying ? 'replaying · temporary' : 'page year'}</span>
            <span aria-live="off" className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums', minWidth: 56, textAlign: 'right' }}>{shown}</span>
          </div>
        </div>
        {frames.missing.length > 0 && (
          <InlineAlert variant="warning">
            No data in this measure for {frames.missing.map((m) => m.name).join(', ')}; {frames.missing.length === 1 ? 'it is' : 'they are'} left out.{frames.notes.length ? ` ${frames.notes.join(' ')}` : ''}
          </InlineAlert>
        )}
        {frames.signed ? (
          <InlineAlert variant="warning">
            Some published shares in this measure are negative (a recorded data deviation), which stacked bars cannot show honestly, so only the table below is drawn.
          </InlineAlert>
        ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <ShareBar title="The stock" subtitle={`Cumulative${frames.cumulativeFrom != null ? ` ${frames.cumulativeFrom}` : ''}–${shown}`} order={order} values={stock} rest={frames.restStock[yi]} tween={!reduceMotion} />
          {flow && frames.restFlow ? (
            <ShareBar title="The flow" subtitle={`Annual, ${shown} only`} order={order} values={flow} rest={frames.restFlow[yi]} tween={!reduceMotion} />
          ) : (
            <p className="__s9cmpx-body4" style={{ margin: 0, color: 'var(--__s9cmpx-static-text-weak)' }}>
              The annual (flow) shares are not published yet in this data release; the stock bar is unaffected.
            </p>
          )}
        </div>
        )}
        <table style={{ width: '100%', maxWidth: 640, marginTop: 12, borderCollapse: 'collapse', fontVariantNumeric: 'tabular-nums' }}>
          <caption className="__s9cmpx-body4" style={{ textAlign: 'left', color: 'var(--__s9cmpx-static-text-weak)', paddingBottom: 4 }}>
            Share by country, {shown}
          </caption>
          <thead>
            <tr className="__s9cmpx-label4" style={{ textAlign: 'right', color: 'var(--__s9cmpx-static-text-weak)' }}>
              <th scope="col" style={{ textAlign: 'left', fontWeight: 600 }}>Country</th>
              <th scope="col" style={{ fontWeight: 600 }}>Stock</th>
              {flow && <th scope="col" style={{ fontWeight: 600 }}>Flow</th>}
            </tr>
          </thead>
          <tbody>
            {order.map((c, i) => (
              <tr key={c.code} className="__s9cmpx-body3" style={{ textAlign: 'right' }}>
                <th scope="row" style={{ textAlign: 'left', fontWeight: 400 }}>
                  <span aria-hidden style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: c.color, marginRight: 8 }} />
                  {c.name}
                </th>
                <td>{fmtShare(stock[i])}</td>
                {flow && <td>{fmtShare(flow[i])}</td>}
              </tr>
            ))}
            <tr className="__s9cmpx-body3" style={{ textAlign: 'right' }}>
              <th scope="row" style={{ textAlign: 'left', fontWeight: 400 }}>
                <span aria-hidden style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: REST_COLOR, marginRight: 8 }} />
                Rest of world
              </th>
              <td>{fmtShare(frames.restStock[yi])}</td>
              {flow && frames.restFlow && <td>{fmtShare(frames.restFlow[yi])}</td>}
            </tr>
            <tr className="__s9cmpx-label4" style={{ textAlign: 'right', borderTop: '1px solid var(--__s9cmpx-static-divider-weak)' }}>
              <th scope="row" style={{ textAlign: 'left' }}>Selected {order.length}</th>
              <td>{fmtShare(sum(stock))}</td>
              {flow && <td>{fmtShare(sum(flow))}</td>}
            </tr>
          </tbody>
        </table>
        <p className="__s9cmpx-body4" style={{ margin: '10px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
          {frames.label} · denominator = sum of national emissions, international aviation and shipping excluded. Replay animates {first} → the page year at about a quarter of a second a year and changes nothing else on the page. Same selected countries in both bars, same colours. Shares describe contribution to emissions; no warming is attributed to a country.
        </p>
      </>
    );
  })();

  const measureControl = (
    <div style={{ maxWidth: '100%', overflowX: 'auto' }}>
      <SegmentedControl
        name="share-measure"
        size="small"
        value={measureId}
        onChange={(v) => setMeasureId(v as ShareMeasureId)}
        items={SHARE_MEASURES.map((m) => ({ value: m.id, label: m.label }))}
      />
    </div>
  );

  return (
    <section id={SHARE_ANCHOR} aria-label="Share of cumulative emissions" style={{ marginBottom: 16 }}>
      <ChartCard
        title={<>Who emitted the stock, and who emits now<YearBadge year={year} /></>}
        headingLevel={2}
      >
        <PurposeLine>compare each selected country&apos;s part of everything emitted so far, by the measure chosen below, with its part of a single year.</PurposeLine>
        {/* Phones: the bars stack under their titles and drop the inline labels (the table below carries every value). */}
        <style>{`@media (max-width: 640px) { .share-bar-row { grid-template-columns: minmax(0, 1fr) !important; gap: 4px !important; } .share-seg-label { display: none; } }`}</style>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 12px', marginBottom: 8 }}>
          {measureControl}
          {frames && (
            <BaselineChip baseline={`cumulative${frames.cumulativeFrom != null ? ` since ${frames.cumulativeFrom}` : ''}`} source="national sum, bunkers excluded" />
          )}
        </div>
        {body}
      </ChartCard>
    </section>
  );
}
