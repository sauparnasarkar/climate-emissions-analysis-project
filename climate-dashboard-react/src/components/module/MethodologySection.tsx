import type { ReactNode } from 'react';
import { InlineAlert } from 'design-system';
import type { CorrelationMetaResponse } from '../../api/correlationTypes';
import { ALL_GAS_START_YEAR } from '../../lib/allGas';
import type { SpliceInfo } from '../../lib/climateSignal';
import { METHODOLOGY_ANCHOR, buildSources, buildTemperatureOffset } from '../../lib/methodology';

const table = { width: '100%', borderCollapse: 'collapse' } as const;
const th = { textAlign: 'left', fontWeight: 600, padding: '6px 10px', verticalAlign: 'bottom' } as const;
const td = { padding: '6px 10px', verticalAlign: 'top', borderTop: '1px solid var(--__s9cmpx-static-divider-weak)' } as const;
const card = { background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, padding: '14px 16px' } as const;
const weak = { color: 'var(--__s9cmpx-static-text-weak)' } as const;

// Requirements §2.5: the baseline each view uses, and why. Fixed copy -- it describes the app's own rules, not data.
const BASELINES: Array<[view: string, baseline: string, why: string]> = [
  ['Overview, Historical Trends, Scenario Comparison', '1990 = 100', 'Matches the machine-learning training window used across the platform'],
  ['Country Profile trend', 'Full OWID history', '1990 is shown as a marker, not as the start'],
  ['All-gas relationship, gas composition', `${ALL_GAS_START_YEAR} onward`, 'Earlier PRIMAP-hist values are reconstructions'],
  ['Long-run CO₂ relationship', '1850–1900 reference', 'Pre-industrial context; keeps early accumulation visible'],
  ['Global, non-ML totals', 'Full available range', 'No model-consistency constraint applies'],
];

/**
 * Methodology & sources (requirements §2.4/§2.5; ENHANCEMENTS.md decision 67, part 9a): where every figure on the page comes from, which baseline each view
 * uses, and why the numbers that look alike differ. The sources table, the temperature offset, the two-totals note and the splice figures are the API's;
 * only the "used for" phrases, the baselines-by-view table and the explanation of why series differ are fixed copy. Each part appears only with its data.
 */
export function MethodologySection({ meta, metaFailed, splice, children }: { meta: CorrelationMetaResponse | null; metaFailed: boolean; splice: SpliceInfo | null; children?: ReactNode }) {
  const sources = buildSources(meta);
  const offset = buildTemperatureOffset(meta);
  return (
    <section id={METHODOLOGY_ANCHOR} aria-labelledby="methodology-heading" style={{ marginBottom: 24 }}>
      <h2 id="methodology-heading" className="__s9cmpx-headline5" style={{ margin: '0 0 8px' }}>Methodology &amp; sources</h2>
      <p className="__s9cmpx-body3" style={{ margin: '0 0 12px', maxWidth: 880 }}>
        Every figure on this page is read from the pipeline output. This section says where each comes from, which baseline each view uses, and why numbers that look alike differ.
      </p>
      {metaFailed && !meta && <InlineAlert variant="warning">The sources, licences and data vintages could not be loaded right now. The baseline rules below do not depend on them.</InlineAlert>}
      {!meta && !metaFailed && <p className="__s9cmpx-body3" style={{ margin: 0 }}>Loading…</p>}

      {sources.length > 0 && (
        <div style={{ ...card, marginBottom: 16, overflowX: 'auto' }}>
          <table style={table}>
            <caption className="__s9cmpx-label3" style={{ textAlign: 'left', paddingBottom: 6 }}>Sources</caption>
            <thead>
              <tr className="__s9cmpx-label4" style={weak}>
                <th scope="col" className="__s9cmpx-label4" style={th}>Source</th>
                <th scope="col" className="__s9cmpx-label4" style={th}>Used for</th>
                <th scope="col" className="__s9cmpx-label4" style={th}>Coverage</th>
                <th scope="col" className="__s9cmpx-label4" style={th}>Vintage</th>
                <th scope="col" className="__s9cmpx-label4" style={th}>Licence</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.name} className="__s9cmpx-body4">
                  <th scope="row" style={{ ...td, textAlign: 'left', fontWeight: 600 }}>{s.name}</th>
                  <td style={td}>{s.usedFor ?? ''}</td>
                  <td style={{ ...td, fontVariantNumeric: 'tabular-nums' }}>{s.coverage ?? ''}</td>
                  <td style={td}>{s.vintage ?? ''}</td>
                  <td style={td}>{s.licences.map((l) => <p key={l} style={{ margin: '0 0 4px' }}>{l}</p>)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ ...card, marginBottom: 16, overflowX: 'auto' }}>
        <table style={table}>
          <caption className="__s9cmpx-label3" style={{ textAlign: 'left', paddingBottom: 6 }}>Baselines by view</caption>
          <thead>
            <tr className="__s9cmpx-label4" style={weak}>
              <th scope="col" className="__s9cmpx-label4" style={th}>View</th>
              <th scope="col" className="__s9cmpx-label4" style={th}>Baseline</th>
              <th scope="col" className="__s9cmpx-label4" style={th}>Why</th>
            </tr>
          </thead>
          <tbody>
            {BASELINES.map(([view, baseline, why]) => (
              <tr key={view} className="__s9cmpx-body4">
                <th scope="row" style={{ ...td, textAlign: 'left', fontWeight: 400 }}>{view}</th>
                <td style={td}>{baseline}</td>
                <td style={td}>{why}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {offset && (
          <p className="__s9cmpx-body4" style={{ margin: '8px 10px 0', ...weak }}>
            The {offset.from}–{offset.to} temperature reference is computed from the Berkeley Earth record itself ({offset.years} years), not taken from the literature: its mean on the dataset&apos;s own
            1951–1980 baseline is {offset.valueC.toFixed(3)} °C, subtracted from every anomaly.
          </p>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
        <div style={card}>
          <div className="__s9cmpx-label3" style={{ marginBottom: 4 }}>Why emissions series differ</div>
          <p className="__s9cmpx-body4" style={{ margin: 0 }}>
            OWID/Global Carbon Project and PRIMAP-hist differ in scope, method, the treatment of bunker fuels and process emissions, and data vintage. Differences between them are expected, not errors.
          </p>
        </div>
        {meta?.two_global_totals && (
          <div style={card}>
            <div className="__s9cmpx-label3" style={{ marginBottom: 4 }}>Two global totals</div>
            <p className="__s9cmpx-body4" style={{ margin: 0 }}>{meta.two_global_totals}</p>
          </div>
        )}
        {splice && (
          <div style={card}>
            <div className="__s9cmpx-label3" style={{ marginBottom: 4 }}>The {splice.year} splice</div>
            <p className="__s9cmpx-body4" style={{ margin: 0 }}>
              Concentration uses Law Dome ice-core values before {splice.year} and Mauna Loa from {splice.year}.
              {splice.overlapYears ? ` Over the overlap years ${splice.overlapYears[0]}–${splice.overlapYears[1]} the two records differ by up to ${splice.maxAbsOverlapGapPpm?.toFixed(1) ?? '—'} ppm` : ''}
              {splice.gapPpm !== null ? `, and by ${Math.abs(splice.gapPpm).toFixed(2)} ppm at the splice itself` : ''}
              {splice.overlapYears ? '.' : ''} The splice year is marked on every concentration chart.
            </p>
          </div>
        )}
      </div>
      {children}
    </section>
  );
}
