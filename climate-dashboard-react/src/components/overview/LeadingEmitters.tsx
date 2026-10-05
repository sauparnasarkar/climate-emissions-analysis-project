import { fmtGt, type Leader } from '../../lib/cumulative';
import { fmtInt } from '../../lib/landingData';

export type MapMode = 'absolute' | 'cumulative';

/** `leaders` carry MtCO₂ in both modes (cumulative ones are shown in Gt).
 * The top-5 leading-emitter ranking beside the map for ALL countries (requirements §2.2 block 3, §2.6; owner decision C): it follows the
 * map's year and its Absolute/Cumulative mode, so the ranking, the tiers and the map always describe the same thing. The shares are
 * shares of the national sum for that year (annual) or of the cumulative total to that year; they describe contribution to emissions
 * only -- no warming is attributed to a country. */
export function LeadingEmitters({ year, mode, leaders, cumulativeFrom }: { year: number; mode: MapMode; leaders: Leader[]; cumulativeFrom: number | null }) {
  const cumulative = mode === 'cumulative';
  const title = cumulative ? `Largest cumulative emitters, to ${year}` : `Leading emitters · ${year}`;
  const subtitle = cumulative ? `GtCO₂ emitted ${cumulativeFrom != null ? `since ${cumulativeFrom}` : 'to date'}, and share of the world total` : 'MtCO₂ in the year, and share of the world total';
  if (leaders.length === 0) return null;
  return (
    <section aria-labelledby="leading-emitters-title" style={{ background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderTop: '3px solid var(--__s9cmpx-accent-secondary, transparent)', borderRadius: 8, padding: '10px 12px' }}>
      <h3 id="leading-emitters-title" className="__s9cmpx-label3" style={{ margin: 0 }}>{title}</h3>
      <p className="__s9cmpx-body4" style={{ margin: '2px 0 6px', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>{subtitle}</p>
      <ol style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
        {leaders.map((l, i) => (
          <li key={l.iso} style={{ display: 'grid', gridTemplateColumns: '18px 1fr auto auto', gap: 8, alignItems: 'baseline' }}>
            <span className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>{i + 1}</span>
            <span className="__s9cmpx-body3">{l.name}</span>
            <span className="__s9cmpx-body3" style={{ fontVariantNumeric: 'tabular-nums' }}>{cumulative ? `${fmtGt(l.value / 1000)} Gt` : `${fmtInt(l.value)} Mt`}</span>
            <span className="__s9cmpx-body4" style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))', minWidth: 44, textAlign: 'right' }}>{l.sharePct.toFixed(1)}%</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
