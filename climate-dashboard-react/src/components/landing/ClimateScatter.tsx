import { useId } from 'react';
import { fmtAnomaly, niceTicks, type Era, type ClimateSignal } from '../../lib/climateSignal';
import { ERA_COLORS, ERA_LABELS } from '../../lib/climateColors';

// Temperature anomaly against cumulative CO₂, one dot per year (Area 2 design, "Shared charts → Scatter").
// Hand-drawn SVG rather than SyChart: it needs era-coloured dots with a fitted line over a numeric x axis, which
// SyChart's line/marker kinds don't do, and the landing already draws its sparklines this way.
// The colours are the design's on-dark chart series colours: the chart always sits on a dark panel (both themes).

const PANEL_INK = '#d7e0f0';
const GRID = 'rgba(148, 180, 192, 0.18)';

const W = 600;
const H = 360;
const M = { l: 48, r: 16, t: 14, b: 46 };

/** What the scatter draws: the dots and the fitted line. A ClimateSignal is one; so is the module's all-gas view. */
export type ScatterData = Pick<ClimateSignal, 'points' | 'line'>;

export interface ScatterAxes {
  /** x-axis title (default: the headline's cumulative CO₂ since 1850) */
  xTitle?: string;
  /** What the x values are called, and their unit, in the screen-reader summary (the visible axis title carries the same unit) */
  xQuantity?: string;
  xUnit?: string;
  /** Tick step on x, and where x starts (default 500 and 0, the headline's axis) */
  xStep?: number;
  xMin?: number;
}

export function ClimateScatter({ signal, xTitle = 'Cumulative CO₂ since 1850 (GtCO₂)', xQuantity = 'cumulative CO₂ since 1850', xUnit = 'GtCO₂', xStep = 500, xMin = 0 }: { signal: ScatterData } & ScatterAxes) {
  const titleId = useId();
  const { points, line } = signal;
  const xMax = Math.ceil(Math.max(...points.map((p) => p.gt)) / xStep) * xStep;
  const yMin = Math.floor(Math.min(...points.map((p) => p.temp)) * 2) / 2;
  const yMax = Math.ceil(Math.max(...points.map((p) => p.temp)) * 2) / 2;
  const sx = (v: number) => M.l + ((v - xMin) / (xMax - xMin)) * (W - M.l - M.r);
  const sy = (v: number) => M.t + (1 - (v - yMin) / (yMax - yMin)) * (H - M.t - M.b);
  const last = points[points.length - 1];
  const first = points[0];
  const summary = `Scatter chart, one dot per year from ${first.year} to ${last.year}. Temperature anomaly rises from ${fmtAnomaly(first.temp)} to ${fmtAnomaly(last.temp)} as ${xQuantity} rises from ${Math.round(first.gt).toLocaleString('en-US')} to ${Math.round(last.gt).toLocaleString('en-US')} ${xUnit}. A fitted line is drawn through the points.`;
  const labelRight = sx(last.gt) > W - 120;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={titleId} style={{ width: '100%', height: 'auto', maxHeight: 'min(56vh, 520px)', display: 'block' }}>
      <title id={titleId}>{summary}</title>
      {niceTicks(yMax, 0.5, yMin).map((t) => (
        <g key={`y${t}`}>
          <line x1={M.l} x2={W - M.r} y1={sy(t)} y2={sy(t)} stroke={GRID} />
          <text x={M.l - 8} y={sy(t)} textAnchor="end" dominantBaseline="middle" fontSize="11" fill={PANEL_INK} opacity="0.75">{t}</text>
        </g>
      ))}
      {niceTicks(xMax, xStep, xMin).map((t) => (
        <text key={`x${t}`} x={sx(t)} y={H - M.b + 16} textAnchor="middle" fontSize="11" fill={PANEL_INK} opacity="0.75">{t.toLocaleString('en-US')}</text>
      ))}
      <text x={M.l} y={H - 6} fontSize="11" fill={PANEL_INK} opacity="0.75">{xTitle}</text>
      <text x={M.l + 4} y={M.t + 10} fontSize="11" fill={PANEL_INK} opacity="0.75">°C above 1850–1900</text>
      <line x1={sx(line.x0)} y1={sy(line.y0)} x2={sx(line.x1)} y2={sy(line.y1)} stroke={PANEL_INK} strokeWidth="1.5" strokeDasharray="5 4" opacity="0.85" />
      {points.map((p) => (
        <circle key={p.year} cx={sx(p.gt)} cy={sy(p.temp)} r="3" fill={ERA_COLORS[p.era]} opacity="0.85" />
      ))}
      <text x={labelRight ? sx(last.gt) - 8 : sx(last.gt) + 8} y={sy(last.temp) - 8} textAnchor={labelRight ? 'end' : 'start'} fontSize="12" fontWeight="600" fill={PANEL_INK}>
        {last.year} · {fmtAnomaly(last.temp)}
      </text>
    </svg>
  );
}

export function ScatterLegend() {
  return (
    <ul style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 14px', margin: 0, padding: 0, listStyle: 'none', fontSize: 12, color: PANEL_INK }}>
      {(Object.keys(ERA_COLORS) as Era[]).map((e) => (
        <li key={e} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: '50%', background: ERA_COLORS[e] }} />
          {ERA_LABELS[e]}
        </li>
      ))}
    </ul>
  );
}
