import { Link } from 'react-router-dom';
import { FORCING_CONCEPT_ONLY } from '../../lib/climateCopy';
import { fmtAnomaly, type ClimateSignal, type YearValue } from '../../lib/climateSignal';
import { fmtInt } from '../../lib/landingData';
import { Sparkline } from './Sparkline';

// The four-step band (Area 2, requirements §2.1): emissions → concentration → radiative forcing → temperature
// anomaly, between the hero and the rest of the page. It shows GLOBAL, ACCUMULATED totals and says so: it never implies
// that one country's emissions in one year set that year's temperature. Forcing is explained, not measured: no number,
// no chart (the platform holds no forcing dataset). Every figure comes from the API.

export const CHAIN_BAND_STYLES = `
.chain-band__steps { display: grid; grid-template-columns: minmax(0, 1fr) 20px minmax(0, 1fr) 20px minmax(0, .85fr) 20px minmax(0, 1fr); gap: 0; list-style: none; margin: 0; padding: 0; align-items: stretch; }
.chain-band__arrow { align-self: center; text-align: center; opacity: .6; }
.chain-band__card { display: flex; flex-direction: column; gap: 8px; padding: 18px; border-radius: 12px; background: var(--__s9cmpx-static-background-weak); border: 1px solid var(--__s9cmpx-static-divider-weak); min-width: 0; }
.chain-band__card--concept { background: transparent; border-style: dashed; }
.chain-band__label { font-family: var(--__s9cmpx-font-families-mono, ui-monospace, monospace); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
.chain-band__spark--emissions { color: #b07a10; } .chain-band__spark--concentration { color: #0A6E8C; } .chain-band__spark--temperature { color: #B3261E; }
[data-theme="analytics"] .chain-band__spark--emissions { color: #e5b955; } [data-theme="analytics"] .chain-band__spark--concentration { color: #5ecbf5; } [data-theme="analytics"] .chain-band__spark--temperature { color: #f2637e; }
.chain-band__label--emissions { color: #b07a10; } .chain-band__label--concentration { color: #0A6E8C; } .chain-band__label--forcing { color: var(--area2-muted, var(--__s9cmpx-static-text-weak)); } .chain-band__label--temperature { color: #B3261E; }
[data-theme="analytics"] .chain-band__label--emissions { color: #e5b955; } [data-theme="analytics"] .chain-band__label--concentration { color: #5ecbf5; } [data-theme="analytics"] .chain-band__label--temperature { color: #f2637e; }
@media (max-width: 1100px) {
  .chain-band__steps { grid-template-columns: 1fr; gap: 12px; }
  .chain-band__arrow { display: none; }
}
`;

export interface ChainBandEmissions {
  /** Latest year and the world total for it, MtCO₂ */
  year: number;
  total: number;
  /** Annual world totals for the sparkline */
  series: YearValue[];
}

function StepValue({ children }: { children: React.ReactNode }) {
  return <div style={{ fontSize: 'clamp(1.5rem, 2.4vw, 2rem)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{children}</div>;
}

const caption = { margin: 0, color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' } as const;

export function ChainBand({ signal, emissions }: { signal: ClimateSignal; emissions: ChainBandEmissions }) {
  const { concentration, temperature, ppm1850, spliceYear, vintageCaveat } = signal;
  const upPct = ppm1850 ? Math.round((concentration.value / ppm1850 - 1) * 100) : null;
  const first = emissions.series[0]?.year;
  return (
    <section aria-labelledby="chain-heading" style={{ padding: 'var(--landing-pad-y) var(--landing-pad-x)', background: 'var(--__s9cmpx-static-background-standard)', display: 'flex', flexDirection: 'column', gap: 24 }}>
      <style>{CHAIN_BAND_STYLES}</style>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px 24px' }}>
        <div>
          <h2 id="chain-heading" className="landing-h2" style={{ margin: 0 }}>The chain reaction, step by step</h2>
          <p className="__s9cmpx-body1" style={{ margin: '8px 0 0', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
            Global totals, built up over time. One country’s emissions in one year do not set that year’s temperature.
          </p>
        </div>
        <Link to="/climate-correlation" style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>Open the Correlation module →</Link>
      </div>
      <ol className="chain-band__steps">
        <li className="chain-band__card">
          <div className="chain-band__label chain-band__label--emissions">01 · Emissions</div>
          <StepValue>{fmtInt(emissions.total)} <span className="__s9cmpx-body3">MtCO₂</span></StepValue>
          <p className="__s9cmpx-body3" style={caption}>Released worldwide in {emissions.year}. Each year adds to the total already in the air.</p>
          <div className="chain-band__spark--emissions"><Sparkline values={emissions.series} /></div>
          {first != null && <p className="__s9cmpx-body4" style={caption}>Annual world totals, {first}–{emissions.series[emissions.series.length - 1].year}</p>}
          <Link to="/overview" style={{ fontWeight: 600, color: 'inherit', textDecoration: 'none' }}>See on the Overview →</Link>
        </li>
        <li className="chain-band__arrow" aria-hidden="true">→</li>
        <li className="chain-band__card">
          <div className="chain-band__label chain-band__label--concentration">02 · Concentration</div>
          <StepValue>{concentration.value.toFixed(1)} <span className="__s9cmpx-body3">ppm</span></StepValue>
          <p className="__s9cmpx-body3" style={caption}>CO₂ in the air, {concentration.year}.{upPct != null ? ` Up ${upPct}% on 1850.` : ''}</p>
          <div className="chain-band__spark--concentration"><Sparkline values={signal.series.concentration} markerYear={spliceYear} /></div>
          {spliceYear != null && <p className="__s9cmpx-body4" style={caption}>Ice core to {spliceYear - 1} · Mauna Loa from {spliceYear}</p>}
        </li>
        <li className="chain-band__arrow" aria-hidden="true">→</li>
        <li className="chain-band__card chain-band__card--concept">
          <div className="chain-band__label chain-band__label--forcing">03 · Radiative forcing · concept only</div>
          <StepValue>Explained, not measured</StepValue>
          <p className="__s9cmpx-body3" style={caption}>{FORCING_CONCEPT_ONLY}</p>
        </li>
        <li className="chain-band__arrow" aria-hidden="true">→</li>
        <li className="chain-band__card">
          <div className="chain-band__label chain-band__label--temperature">04 · Temperature anomaly</div>
          <StepValue>{fmtAnomaly(temperature.value)}</StepValue>
          <p className="__s9cmpx-body3" style={caption}>{temperature.year}, above the 1850–1900 average.</p>
          <div className="chain-band__spark--temperature"><Sparkline values={signal.series.temperature} /></div>
          {/* The caveat names its source itself; without one, name it here. */}
          <p className="__s9cmpx-body4" style={caption}>{vintageCaveat ?? 'Berkeley Earth'}</p>
        </li>
      </ol>
    </section>
  );
}
