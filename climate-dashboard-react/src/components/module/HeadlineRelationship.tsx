import { ChartCard } from 'design-system';
import { useSectionIds } from './useSectionIds';
import { ALL_GAS_START_YEAR } from '../../lib/allGas';
import { GLOBAL_RELATIONSHIP_ANCHOR, NOT_A_CLIMATE_MODEL } from '../../lib/climateCopy';
import { pairedEndNote, type ClimateSignal } from '../../lib/climateSignal';
import type { Headline } from '../../lib/headline';
import { BaselineChip } from '../climate/BaselineChip';
import { CHART_PANEL_STYLES } from '../climate/chartPanel';
import { PurposeLine } from '../climate/PurposeLine';
import { ClimateScatter, ScatterLegend } from '../landing/ClimateScatter';
import { Ar6Strip } from './Ar6Strip';

const card = { background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, padding: '14px 16px' } as const;
const mono = { fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)' } as const;

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>{k}</dt>
      <dd className="__s9cmpx-body3" style={{ margin: 0, fontVariantNumeric: 'tabular-nums', textAlign: 'right' }}>{v}</dd>
    </>
  );
}

/**
 * The module's headline relationship (requirements §1.3.1; ENHANCEMENTS.md decision 65): the era-coloured scatter of temperature anomaly against
 * cumulative CO₂ since 1850, the warming-per-1,000-GtCO₂ stat card with its interval, fit quality and the labelled fossil-only comparison, the AR6
 * strip, and the baseline card. Descriptive: the caption says correlation, not proof of cause, and the card says it is not a climate model.
 */
const EMBEDDED_STACK = '.module-embedded-grid[data-embedded] { grid-template-columns: minmax(0, 1fr) !important; }';

export function HeadlineRelationship({ signal, headline, hasAllGas = false, embedded }: { signal: ClimateSignal; headline: Headline; hasAllGas?: boolean; embedded?: boolean }) {
  const ids = useSectionIds(embedded, GLOBAL_RELATIONSHIP_ANCHOR, 'global-relationship-heading');
  const Heading = embedded ? 'h3' : 'h2'; // inside an answer the question is the h2
  const { slope, ciLow, ciHigh, rSquared, start, end, nYears, fossilSlope } = headline;
  const excluded = signal.omittedYears.length ? signal.omittedYears.join(', ') : 'None';
  return (
    <section id={ids.sectionId} aria-labelledby={ids.headingId} style={{ marginBottom: 24 }}>
      <style>{CHART_PANEL_STYLES + '@media (max-width: 1100px) { .module-relationship-grid { grid-template-columns: 1fr !important; } }' + EMBEDDED_STACK}</style>
      <Heading id={ids.headingId} className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>Global relationship</Heading>
      <div className="module-relationship-grid module-embedded-grid" data-embedded={embedded || undefined} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.55fr) minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <ChartCard title={`Temperature anomaly vs cumulative CO₂, ${start}–${end}`} headingLevel={embedded ? 4 : 3}>
          <PurposeLine>show how warming tracks the total CO₂ emitted so far, rather than any single year.</PurposeLine>
          <div className="climate-chart-panel">
            <ScatterLegend />
            <ClimateScatter signal={signal} />
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginTop: 8 }}>
            <BaselineChip baseline="1850–1900" source="Berkeley Earth" />
            <span className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>
              Each dot is one year. Dashed line: least-squares fit. Co-movement is shown as context, not as proof of cause.{pairedEndNote(signal) ? ` ${pairedEndNote(signal)}` : ''}{hasAllGas ? ` The recent all-gas view (${ALL_GAS_START_YEAR} onward) is a separate chart below and is not called TCRE.` : ''}
            </span>
          </div>
        </ChartCard>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={card}>
            <div className="__s9cmpx-label3">Warming per 1,000 GtCO₂</div>
            <div className="__s9cmpx-headline2" style={{ fontVariantNumeric: 'tabular-nums', margin: '4px 0 8px' }}>{slope.toFixed(3)} <span className="__s9cmpx-body2">°C</span></div>
            <dl style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '4px 12px', margin: 0 }}>
              <Row k="95% CI (Newey–West HAC)" v={`${ciLow.toFixed(3)}–${ciHigh.toFixed(3)}`} />
              {rSquared !== null && <Row k="R²" v={rSquared.toFixed(2)} />}
              <Row k="Years" v={`${start}–${end} (${nYears})`} />
              {fossilSlope !== null && <Row k="Fossil + cement only" v={fossilSlope.toFixed(3)} />}
            </dl>
            <div style={{ marginTop: 12, color: 'var(--__s9cmpx-static-text-standard)' }}>
              <Ar6Strip slope={slope} fossilSlope={fossilSlope} />
            </div>
            <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
              A data-driven analog to the IPCC&apos;s TCRE, not a restatement of it: this regression also absorbs warming from other gases and aerosols that varies with CO₂, and
              depends on uncertain land-use estimates. {NOT_A_CLIMATE_MODEL}
            </p>
          </div>

          <div style={card}>
            <div className="__s9cmpx-label3" style={{ marginBottom: 6 }}>Baseline</div>
            <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', margin: 0 }}>
              <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Reference</dt>
              <dd className="__s9cmpx-body3" style={{ margin: 0 }}>1850–1900 mean</dd>
              <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Formula</dt>
              <dd className="__s9cmpx-body3" style={{ margin: 0, ...mono }}>ΔT = T − mean(T₁₈₅₀–₁₉₀₀)</dd>
              <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Range</dt>
              <dd className="__s9cmpx-body3" style={{ margin: 0 }}>{start}–{end}</dd>
              <dt className="__s9cmpx-body4" style={{ color: 'var(--__s9cmpx-static-text-weak)' }}>Excluded</dt>
              <dd className="__s9cmpx-body3" style={{ margin: 0 }}>{excluded}</dd>
            </dl>
            {signal.vintageCaveat && (
              <p role="note" className="__s9cmpx-body4" style={{ margin: '10px 0 0', color: 'var(--area2-warning, #6E4800)' }}>{signal.vintageCaveat}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
