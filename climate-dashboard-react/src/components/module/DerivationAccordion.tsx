import { useState, type ReactNode } from 'react';
import { Accordion } from 'design-system';
import { NO_COUNTRY_ATTRIBUTION, NOT_A_CLIMATE_MODEL } from '../../lib/climateCopy';
import { DERIVATION_ANCHOR, type Derivation } from '../../lib/derivation';

const th = { textAlign: 'right', fontWeight: 600, padding: '4px 10px' } as const;
const td = { textAlign: 'right', padding: '4px 10px', borderTop: '1px solid var(--__s9cmpx-static-divider-weak)', fontVariantNumeric: 'tabular-nums' } as const;
const first = { textAlign: 'left' } as const;
const body = { fontSize: 14, lineHeight: 1.6, maxWidth: 900, padding: '4px 0 8px' } as const;

const f3 = (v: number) => v.toFixed(3);

function Table({ caption, head, rows }: { caption: string; head: string[]; rows: ReactNode[][] }) {
  return (
    <div style={{ overflowX: 'auto', margin: '8px 0' }}>
      <table style={{ borderCollapse: 'collapse', minWidth: 320 }}>
        <caption className="__s9cmpx-body4" style={{ textAlign: 'left', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))', paddingBottom: 2 }}>{caption}</caption>
        <thead>
          <tr className="__s9cmpx-label4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>
            {head.map((h, i) => <th key={h} scope="col" className="__s9cmpx-label4" style={{ ...th, ...(i === 0 ? first : {}) }}>{h}</th>)}
          </tr>
        </thead>
        <tbody className="__s9cmpx-body4">
          {rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j} style={{ ...td, ...(j === 0 ? first : {}) }}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * "How this number was derived" (requirements §1.3.1; ENHANCEMENTS.md decision 67, part 9b): the headline slope's derivation in seven steps, one open
 * at a time with the first open. Every figure and every sentence about the method is the headline response's own (its fit, its fit_context and its
 * attribution); only the closing "what this is not" step is fixed copy. A step whose data is missing is left out rather than shown with gaps.
 */
export function DerivationAccordion({ derivation }: { derivation: Derivation }) {
  const { regression: r, uncertainty: u, sensitivity: s, stability: st, ar6, attribution } = derivation;
  const steps: Array<{ title: string; content: ReactNode }> = [];

  steps.push({
    title: 'What is regressed on what',
    content: (
      <div style={body}>
        <p style={{ margin: '0 0 8px' }}>
          {r.label}. The slope is the change in <strong>{r.yName}</strong> per unit of <strong>{r.xName}</strong>, over {r.start}–{r.end} ({r.n} years): {f3(r.slope)} {r.unit}
          {r.rSquared !== null ? `, with R² ${r.rSquared.toFixed(2)}` : ''}.
        </p>
        {r.method && <p style={{ margin: '0 0 8px' }}>Method: {r.method}.</p>}
        {r.xDescription && <p style={{ margin: '0 0 8px' }}>{r.xDescription}</p>}
        {r.yDescription && <p style={{ margin: '0 0 8px' }}>{r.yDescription}</p>}
        {r.methodology && <p style={{ margin: 0 }}>{r.methodology}</p>}
      </div>
    ),
  });

  if (u) {
    steps.push({
      title: 'Uncertainty',
      content: (
        <div style={body}>
          {u.seOls !== null && u.seHac !== null && (
            <p style={{ margin: '0 0 8px' }}>
              The ordinary least-squares standard error of the slope is {f3(u.seOls)}; the Newey–West (HAC) standard error is {f3(u.seHac)}
              {u.lag1 !== null ? `, because the residuals are autocorrelated (lag-1 ${u.lag1.toFixed(2)}${u.durbinWatson !== null ? `, Durbin–Watson ${u.durbinWatson.toFixed(2)}` : ''})` : ''}.
              {u.seHac > u.seOls ? ' Ignoring that autocorrelation would understate the uncertainty.' : ''}
            </p>
          )}
          {u.rule && <p style={{ margin: '0 0 8px' }}>{u.rule}.</p>}
          {u.sensitivity.length > 0 && (
            <Table
              caption="Sensitivity of the interval to the lag length"
              head={['maxlags', 'HAC standard error', '95% interval']}
              rows={u.sensitivity.map((x) => [x.maxlags, x.seHac !== null ? f3(x.seHac) : '', `${f3(x.ciLow)}–${f3(x.ciHigh)}`])}
            />
          )}
        </div>
      ),
    });
  }

  if (s) {
    steps.push({
      title: 'How sensitive the slope is',
      content: (
        <div style={body}>
          {s.landUseScale.length > 0 && (
            <Table caption="Scaling the land-use emissions" head={['Land-use scale', `Slope (${r.unit})`]} rows={s.landUseScale.map((x) => [`×${x.scale}`, f3(x.slope)])} />
          )}
          {s.weightScan && (
            <>
              {s.weightScan.definition && <p style={{ margin: '8px 0 0' }}>{s.weightScan.definition}.</p>}
              <Table
                caption={`Weight on land-use CO₂${s.weightScan.split !== null ? `, holdout from ${s.weightScan.split}` : ''}`}
                head={['Weight', 'Slope', 'R²', 'Holdout RMSE (°C)']}
                rows={s.weightScan.rows.map((x) => [x.weight, f3(x.slope), x.rSquared !== null ? x.rSquared.toFixed(3) : '', x.holdoutRmse !== null ? x.holdoutRmse.toFixed(3) : ''])}
              />
              {s.weightScan.note && <p style={{ margin: 0 }}>{s.weightScan.note}</p>}
            </>
          )}
        </div>
      ),
    });
  }

  if (st) {
    steps.push({
      title: 'Stability',
      content: (
        <div style={body}>
          {st.summary && <p style={{ margin: '0 0 8px' }}>{st.summary}</p>}
          {st.bootstrap && (
            <p style={{ margin: '0 0 8px' }}>
              Residual block bootstrap ({st.resamples !== null ? `${st.resamples.toLocaleString('en-US')} resamples` : 'resamples'}{st.seed !== null ? `, seed ${st.seed}` : ''}): 95% interval {f3(st.bootstrap.low)}–{f3(st.bootstrap.high)} with {st.bootstrap.blockYears}-year blocks
              {st.hac ? `, against ${f3(st.hac[0])}–${f3(st.hac[1])} from the Newey–West standard errors` : ''}.
            </p>
          )}
          {st.blockSensitivity.length > 0 && (
            <Table caption="Block-length sensitivity" head={['Block (years)', '95% interval', 'Median']} rows={st.blockSensitivity.map((b) => [b.blockYears, `${f3(b.low)}–${f3(b.high)}`, b.median !== null ? f3(b.median) : ''])} />
          )}
          {st.holdouts.length > 0 && (
            <Table
              caption="Decade holdouts: fit on the earlier years, predict the later ones"
              head={['Split', 'Fitted on', 'Predicted', 'Slope', 'RMSE (°C)', 'Baseline RMSE (°C)']}
              rows={st.holdouts.map((h) => [h.split, h.train ? `${h.train[0]}–${h.train[1]}` : '', h.test ? `${h.test[0]}–${h.test[1]}` : '', h.trainSlope !== null ? f3(h.trainSlope) : '', h.rmse.toFixed(3), h.baselineRmse !== null ? h.baselineRmse.toFixed(3) : ''])}
            />
          )}
          {st.note && <p style={{ margin: 0 }}>{st.note}</p>}
        </div>
      ),
    });
  }

  if (ar6) {
    steps.push({
      title: 'Comparison with the IPCC range',
      content: (
        <div style={body}>
          <p style={{ margin: '0 0 8px' }}>
            The IPCC AR6 very likely range for the transient climate response to cumulative emissions is {ar6.low}–{ar6.high} {r.unit}, best estimate {ar6.best}.
            {` This slope (${f3(r.slope)})`}
            {ar6.within !== null ? ` ${ar6.within ? 'lies within' : 'lies outside'} that range` : ''}
            {ar6.ratio !== null ? `${ar6.within !== null ? ' and' : ''} is ${ar6.ratio.toFixed(2)}× the best estimate` : ''}
            {ar6.overlaps !== null ? `; its 95% interval ${ar6.overlaps ? 'overlaps' : 'does not overlap'} the range` : ''}.
          </p>
          {ar6.source && <p style={{ margin: '0 0 8px' }}>{ar6.source}</p>}
          {ar6.note && <p style={{ margin: 0 }}>{ar6.note}</p>}
        </div>
      ),
    });
  }

  if (attribution.length > 0) {
    steps.push({
      title: 'Data, licences and attribution',
      content: (
        <div style={body}>
          {attribution.map((a) => (
            <div key={`${a.series ?? ''}${a.source}`} style={{ margin: '0 0 12px' }}>
              <strong>{a.source}</strong>
              {a.license && <p style={{ margin: '2px 0 0' }}>{a.license}</p>}
              {a.note && <p style={{ margin: '2px 0 0' }}>{a.note}</p>}
              {a.citations.length > 0 && (
                <ul style={{ margin: '4px 0 0', paddingLeft: 18 }}>
                  {a.citations.map((c) => <li key={c}>{c}</li>)}
                </ul>
              )}
            </div>
          ))}
        </div>
      ),
    });
  }

  steps.push({
    title: 'What this is not',
    content: (
      <ul style={{ ...body, margin: 0, paddingLeft: 20 }}>
        <li>{NOT_A_CLIMATE_MODEL}</li>
        <li>A correlation between the CO₂ emitted so far and the temperature record: context, not proof of cause.</li>
        <li>An analog to the IPCC&apos;s TCRE, not a restatement of it: it also absorbs warming from other gases and aerosols that varies with CO₂, and rests on uncertain land-use estimates.</li>
        <li>{NO_COUNTRY_ATTRIBUTION}</li>
      </ul>
    ),
  });

  const items = steps.map((s, i) => ({
    id: `derive-${i + 1}`,
    title: (
      <span style={{ display: 'inline-flex', alignItems: 'baseline', gap: 12 }}>
        <span style={{ fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)', fontSize: 12, opacity: 0.7 }}>{String(i + 1).padStart(2, '0')}</span>
        {s.title}
      </span>
    ),
    content: s.content,
  }));
  // One open at a time, the first by default.
  const [open, setOpen] = useState<string[]>([items[0].id]);

  return (
    <div id={DERIVATION_ANCHOR} style={{ background: 'var(--__s9cmpx-static-background-standard)', border: '1px solid var(--__s9cmpx-static-divider-weak)', borderRadius: 8, padding: '14px 16px', marginTop: 16 }}>
      <h3 className="__s9cmpx-headline6" style={{ margin: 0 }}>How this number was derived</h3>
      <p className="__s9cmpx-body4" style={{ margin: '2px 0 8px', color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>Every figure below is read from the pipeline output.</p>
      <Accordion items={items} openIds={open} onOpenChange={setOpen} />
    </div>
  );
}
