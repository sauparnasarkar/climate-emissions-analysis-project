import { Link } from 'react-router-dom';
import { FORECAST_END_YEAR } from '../../constants';
import { fmtAnomaly, type ClimateSignal } from '../../lib/climateSignal';
import { CLIMATE_SIGNAL_ANCHOR, NOT_A_CLIMATE_MODEL } from '../../lib/climateCopy';
import { CHART_PANEL_STYLES } from '../climate/chartPanel';
import { BaselineChip } from '../climate/BaselineChip';
import { SourceNote } from '../climate/SourceNote';
import { PHONE_QUERY, useMediaQuery } from '../../hooks/useMediaQuery';
import { ctaClass } from './cta';
import { ClimateScatter, ScatterLegend } from './ClimateScatter';

// Banner 1 of the landing carousel (Area 2, requirements §2.1): the climate signal, read from the correlation
// API. It states a long-run, global, cumulative relationship -- never that one country's or one year's
// emissions set that year's temperature.

export const CLIMATE_BANNER_STYLES = CHART_PANEL_STYLES + `
.climate-banner { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: clamp(32px, 4vw, 56px); align-items: center; padding: clamp(16px, 3vh, 48px) var(--landing-pad-x); }
.climate-banner__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 1px solid var(--__s9cmpx-static-divider-weak); border-bottom: 1px solid var(--__s9cmpx-static-divider-weak); }
.climate-banner__metrics > div { padding: 14px 14px 14px 0; }
.climate-banner__metrics > div + div { padding-left: 14px; border-left: 1px solid var(--__s9cmpx-static-divider-weak); }
/* Text on the page background (not on the dark chart panel): the design's per-theme series colours. */
.climate-metric--temperature { color: #f2637e; }
.climate-metric--concentration { color: #5ecbf5; }
[data-theme="analytics-bright-tidewater"] .climate-metric--temperature { color: #B3261E; }
[data-theme="analytics-bright-tidewater"] .climate-metric--concentration { color: #0A6E8C; }
@media (max-width: 1100px) { .climate-banner { grid-template-columns: 1fr; } }
/* Phones (decision 72): temperature and CO₂ as two side-by-side cards (the slope, the third, is dropped here), full-width stacked buttons, tighter spacing. */
@media (max-width: 640px) {
  .climate-banner { gap: 14px; padding-top: 12px; padding-bottom: 8px; }
  /* As in the design frame: copy, the two figures, the chart, then the buttons (the buttons are placed after the chart in the markup on a phone, so reading and focus order match). */
  .climate-banner__text > p { font-size: 0.9375rem !important; line-height: 1.45; }
  .climate-banner__chart { padding: 12px 14px; gap: 8px; }
  .climate-banner__forecasts { display: none; }
  .climate-banner__chart figcaption { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .climate-banner__metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; border: 0; }
  .climate-banner__metrics > div, .climate-banner__metrics > div + div { padding: 10px 12px; border: 1px solid var(--__s9cmpx-static-divider-weak); border-radius: 8px; } /* no fill: the figures keep the contrast they were audited against on the page background */
  .climate-banner__metrics > div:nth-child(3) { display: none; }
  .climate-banner__ctas { flex-direction: column; align-items: stretch !important; gap: 8px !important; }
  .climate-banner__ctas > a:not([class*="button"]) { text-align: center; padding: 6px 0; }
  .climate-banner__ctas > a[class*="button"] { justify-content: center; }
}
`;

function Metric({ value, caption, tone }: { value: string; caption: string; tone?: 'temperature' | 'concentration' }) {
  return (
    <div>
      <div className={tone ? `climate-metric--${tone}` : undefined} style={{ fontSize: 'clamp(1.25rem, 2.2vw, 1.75rem)', fontWeight: 600, fontVariantNumeric: 'tabular-nums', ...(tone ? {} : { color: 'var(--__s9cmpx-static-text-strong)' }) }}>{value}</div>
      <div className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{caption}</div>
    </div>
  );
}

export function ClimateSignalBanner({ signal, headingId }: { signal: ClimateSignal; headingId: string }) {
  const { fit, temperature, concentration } = signal;
  // On a phone the buttons come after the chart in the markup too (not just visually), so reading and focus order match what is seen.
  const isPhone = useMediaQuery(PHONE_QUERY);
  const ctas = (
    <div className="climate-banner__ctas" style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
      <Link to={`/overview#${CLIMATE_SIGNAL_ANCHOR}`} className={ctaClass('primary')} style={{ textDecoration: 'none' }}>See the climate signal</Link>
      <Link to="/climate-correlation" className={ctaClass('secondary')} style={{ textDecoration: 'none' }}>Explore climate correlation</Link>
      <Link to="/forecasts" className="climate-banner__forecasts" style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>Forecasts to {FORECAST_END_YEAR} →</Link>
    </div>
  );
  return (
    <div className="climate-banner">
      <div className="climate-banner__text" style={{ display: 'flex', flexDirection: 'column', gap: 'clamp(12px, 2.2vh, 24px)', minWidth: 0 }}>
        <div className="__s9cmpx-label3" style={{ letterSpacing: '0.08em', lineHeight: 1.5, textTransform: 'uppercase', color: 'var(--__s9cmpx-static-text-accent, inherit)' }}>
          Climate signal · Global · {fit.start}–{fit.end}
        </div>
        <h1 id={headingId} style={{ margin: 0, fontSize: 'clamp(1.75rem, min(4.6vw, 5.8vh), 3.75rem)', lineHeight: 1.05, fontWeight: 700 }}>
          Global temperature has risen with the CO₂ we have accumulated.
        </h1>
        <p className="__s9cmpx-body1" style={{ margin: 0, fontSize: 'clamp(1rem, 1.4vw, 1.125rem)', color: 'var(--__s9cmpx-static-text-weak)' }}>
          Emissions set off a chain reaction: CO₂ builds up in the atmosphere, traps more heat, and the planet warms. Over {fit.nYears} years, warming has followed the cumulative total, not any single year’s emissions.
        </p>
        <div className="climate-banner__metrics">
          <Metric value={fmtAnomaly(temperature.value)} caption={`${temperature.year}, vs 1850–1900`} tone="temperature" />
          <Metric value={`${concentration.value.toFixed(1)} ppm`} caption={`Atmospheric CO₂, ${concentration.year}`} tone="concentration" />
          <Metric value={`${fit.slope.toFixed(2)} °C`} caption="per 1,000 GtCO₂ emitted" />
        </div>
        {!isPhone && ctas}
      </div>
      <figure className="climate-chart-panel climate-banner__chart" style={{ margin: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
          <figcaption style={{ fontWeight: 600 }}>Temperature anomaly vs cumulative CO₂</figcaption>
          <ScatterLegend />
        </div>
        <ClimateScatter signal={signal} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <BaselineChip inChartPanel baseline="1850–1900" source="Berkeley Earth" />
          <span className="__s9cmpx-body4">Global series. Long-term co-movement. {NOT_A_CLIMATE_MODEL}</span>
        </div>
        <SourceNote inChartPanel sources={['Berkeley Earth', 'OWID + Global Carbon Project', 'NOAA GML + Law Dome']}>{signal.vintageCaveat ?? undefined}</SourceNote>
      </figure>
      {isPhone && ctas}
    </div>
  );
}
