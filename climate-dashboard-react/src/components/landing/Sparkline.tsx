import type { YearValue } from '../../lib/climateSignal';

/** A small axis-less trend line (2 px stroke, non-scaling, drawn in the parent's text colour so the band can theme it) with an
 * optional dashed vertical marker at a year -- the landing's four-step band. Decorative: the figure beside it carries the information, so it is hidden from assistive tech. */
export function Sparkline({ values, markerYear, highlightYear }: { values: YearValue[]; markerYear?: number | null; highlightYear?: number | null }) {
  if (values.length < 2) return null;
  const W = 240;
  const H = 48;
  const x0 = values[0].year;
  const x1 = values[values.length - 1].year;
  const lo = Math.min(...values.map((v) => v.value));
  const hi = Math.max(...values.map((v) => v.value));
  const sx = (y: number) => ((y - x0) / (x1 - x0 || 1)) * W;
  const sy = (v: number) => H - 3 - ((v - lo) / (hi - lo || 1)) * (H - 6);
  const d = values.map((p, i) => `${i === 0 ? 'M' : 'L'}${sx(p.year).toFixed(1)} ${sy(p.value).toFixed(1)}`).join(' ');
  const marker = markerYear != null && markerYear > x0 && markerYear < x1 ? sx(markerYear) : null;
  // The "you are here" point: a drop line and a dot at the year the page is showing (the Overview map's selected year).
  const hl = highlightYear != null ? values.find((v) => v.year === highlightYear) : undefined;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} aria-hidden="true" focusable="false" style={{ display: 'block' }}>
      {marker != null && <line x1={marker} x2={marker} y1={0} y2={H} stroke="currentColor" strokeOpacity="0.55" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />}
      {hl && <line x1={sx(hl.year)} x2={sx(hl.year)} y1={sy(hl.value)} y2={H} stroke="currentColor" strokeOpacity="0.55" vectorEffect="non-scaling-stroke" />}
      <path d={d} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      {hl && <circle cx={sx(hl.year)} cy={sy(hl.value)} r="3.5" fill="currentColor" />}
    </svg>
  );
}
