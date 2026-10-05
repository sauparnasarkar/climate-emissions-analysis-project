import { CAUSAL_CHAIN, CAUSAL_CHAIN_ANCHOR, FORCING_CONCEPT_ONLY } from '../../lib/climateCopy';
import { fmtAnomaly, type ClimateSignal } from '../../lib/climateSignal';
import { fmtInt } from '../../lib/landingData';
import { BaselineChip } from '../climate/BaselineChip';

export interface ChainEmissions {
  year: number;
  /** World annual CO₂, MtCO₂ */
  total: number;
}

const cell = { display: 'flex', flexDirection: 'column', gap: 6, padding: '14px 16px', minWidth: 0 } as const;
const label = { fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase' } as const;
const weak = { margin: 0, color: 'var(--__s9cmpx-static-text-weak)' } as const;

/**
 * The causal chain as four cells in one strip (requirements §2.4): emissions → concentration → radiative forcing → temperature anomaly. These are
 * GLOBAL, ACCUMULATED quantities and the copy says so. Forcing is a concept only -- no value, no chart (the platform holds no forcing dataset).
 * Every figure is read from the API; a cell whose figure is missing says nothing rather than showing a zero.
 */
export function CausalChain({ signal, emissions }: { signal: ClimateSignal; emissions: ChainEmissions | null }) {
  const { concentration, temperature, ppm1850 } = signal;
  const [emissionsName, concentrationName, forcingName, temperatureName] = CAUSAL_CHAIN;
  return (
    <section id={CAUSAL_CHAIN_ANCHOR} aria-labelledby="causal-chain-heading" style={{ marginBottom: 24 }}>
      <h2 id="causal-chain-heading" className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>Causal chain</h2>
      <style>{'.module-chain { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--__s9cmpx-static-divider-weak); border-radius: 8px; overflow: hidden; background: var(--__s9cmpx-static-background-standard); list-style: none; margin: 0; padding: 0; } .module-chain > li + li { border-left: 1px solid var(--__s9cmpx-static-divider-weak); } .module-chain__forcing { background: repeating-linear-gradient(135deg, transparent 0 7px, var(--__s9cmpx-static-divider-weak) 7px 8px); } @media (max-width: 900px) { .module-chain { grid-template-columns: 1fr; } .module-chain > li + li { border-left: 0; border-top: 1px solid var(--__s9cmpx-static-divider-weak); } }'}</style>
      <ol className="module-chain">
        <li style={cell}>
          <span style={label}>1 · {emissionsName}</span>
          {emissions ? (
            <>
              <strong className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtInt(emissions.total)} <span className="__s9cmpx-body3">MtCO₂ in {emissions.year}</span></strong>
              <p className="__s9cmpx-body4" style={weak}>World annual CO₂. Each year&apos;s emissions add to a stock that stays.</p>
              <BaselineChip baseline="none · annual level" source="OWID" />
            </>
          ) : (
            <p className="__s9cmpx-body4" style={weak}>Each year&apos;s emissions add to a stock that stays.</p>
          )}
        </li>
        <li style={cell}>
          <span style={label}>2 · {concentrationName}</span>
          <strong className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums' }}>{concentration.value.toFixed(1)} <span className="__s9cmpx-body3">ppm in {concentration.year}</span></strong>
          <p className="__s9cmpx-body4" style={weak}>About half of emitted CO₂ stays in the air{ppm1850 !== null ? `: ${ppm1850.toFixed(0)} ppm in 1850` : ''}.</p>
          <BaselineChip baseline="1850" source="NOAA + Law Dome" />
        </li>
        <li style={cell} className="module-chain__forcing">
          <span style={label}>3 · {forcingName} · concept</span>
          <p className="__s9cmpx-body3" style={{ margin: 0 }}>Not calculated here.</p>
          <p className="__s9cmpx-body4" style={weak}>{FORCING_CONCEPT_ONLY}</p>
        </li>
        <li style={cell}>
          <span style={label}>4 · {temperatureName}</span>
          <strong className="__s9cmpx-headline5" style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtAnomaly(temperature.value)} <span className="__s9cmpx-body3">in {temperature.year}</span></strong>
          <p className="__s9cmpx-body4" style={weak}>Global surface temperature above the 1850–1900 mean.</p>
          <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
        </li>
      </ol>
    </section>
  );
}
