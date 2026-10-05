import { useId } from 'react';
import { AR6_TCRE } from '../../lib/climateCopy';
import { ERA_COLORS } from '../../lib/climateColors';

const AXIS_MIN = 0.2;
const AXIS_MAX = 0.9;
const W = 320;
const PAD = 14;

/**
 * Where the regression's slopes sit against the IPCC AR6 very-likely range for the transient climate response to cumulative emissions
 * (requirements §1.3.1). The band and its 0.45 best estimate are fixed comparison copy; the two markers are this platform's slopes.
 * A comparison of magnitudes, not a claim that the two measure the same thing -- the methodology note says how they differ.
 */
export function Ar6Strip({ slope, fossilSlope }: { slope: number; fossilSlope: number | null }) {
  const titleId = useId();
  const x = (v: number) => PAD + ((v - AXIS_MIN) / (AXIS_MAX - AXIS_MIN)) * (W - 2 * PAD);
  const inRange = (v: number) => v >= AXIS_MIN && v <= AXIS_MAX;
  const summary = `Comparison strip, °C per 1,000 GtCO₂ on an axis from ${AXIS_MIN} to ${AXIS_MAX}. The IPCC AR6 very likely range is ${AR6_TCRE.low} to ${AR6_TCRE.high}, best estimate ${AR6_TCRE.best}. This regression's total CO₂ slope is ${slope.toFixed(3)}${fossilSlope !== null ? ` and its fossil and cement only slope is ${fossilSlope.toFixed(3)}` : ''}.`;
  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${W} 74`} role="img" aria-labelledby={titleId} style={{ width: '100%', height: 'auto', display: 'block' }}>
        <title id={titleId}>{summary}</title>
        <rect x={x(AXIS_MIN)} y="30" width={x(AXIS_MAX) - x(AXIS_MIN)} height="8" rx="4" fill="currentColor" opacity="0.12" />
        <rect x={x(AR6_TCRE.low)} y="30" width={x(AR6_TCRE.high) - x(AR6_TCRE.low)} height="8" rx="4" fill="#0A6E8C" opacity="0.55" />
        <line x1={x(AR6_TCRE.best)} x2={x(AR6_TCRE.best)} y1="26" y2="42" stroke="currentColor" strokeWidth="1.5" opacity="0.8" />
        {fossilSlope !== null && inRange(fossilSlope) && <circle cx={x(fossilSlope)} cy="34" r="6" fill={ERA_COLORS.y1900_1969} stroke="#fff" strokeWidth="1.5" />}
        {inRange(slope) && <circle cx={x(slope)} cy="34" r="6" fill="#fff" stroke="currentColor" strokeWidth="1.5" />}
        {[0.2, 0.4, 0.6, 0.8].map((t) => (
          <text key={t} x={x(t)} y="62" textAnchor="middle" fontSize="10" fill="currentColor" opacity="0.7" fontFamily="var(--__s9cmpx-font-families-mono, ui-monospace, monospace)">{t.toFixed(1)}</text>
        ))}
        <text x={x(AR6_TCRE.best)} y="18" textAnchor="middle" fontSize="10" fill="currentColor" opacity="0.8" fontFamily="var(--__s9cmpx-font-families-mono, ui-monospace, monospace)">AR6 {AR6_TCRE.best.toFixed(2)}</text>
      </svg>
      <figcaption className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
        <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#fff', border: '1.5px solid currentColor', marginRight: 6, verticalAlign: 'middle' }} />
        Total CO₂ {slope.toFixed(3)}
        {fossilSlope !== null && (
          <>
            {' · '}
            <span aria-hidden="true" style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: ERA_COLORS.y1900_1969, marginRight: 6, verticalAlign: 'middle' }} />
            Fossil + cement only {fossilSlope.toFixed(3)}
          </>
        )}
        {' · '}
        <span aria-hidden="true" style={{ display: 'inline-block', width: 14, height: 8, borderRadius: 4, background: '#0A6E8C', opacity: 0.55, marginRight: 6, verticalAlign: 'middle' }} />
        IPCC AR6 very likely range {AR6_TCRE.low}–{AR6_TCRE.high}
      </figcaption>
    </figure>
  );
}
