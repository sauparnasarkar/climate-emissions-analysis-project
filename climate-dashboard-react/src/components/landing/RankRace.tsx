import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Slider, useReducedMotion } from 'design-system';
import type { WorldMapTimeSeries } from '../../api/types';
import { MAX_SELECTED_COUNTRIES } from '../../constants';
import { buildRaceModel, fmtInt, raceFrame, raceShare, RACE_SIZE } from '../../lib/landingData';
import { VISUALLY_HIDDEN } from '../../lib/visuallyHidden';

const YEAR_STEP_MS = 550;
const ROW_PITCH = 46;
const ROW_HEIGHT = 36;

/** The ten largest emitters, year by year (real per-year values from the world-map series), with
 * rows that re-rank as the years advance. One step per year; CSS handles the movement, not
 * per-frame React updates. Autoplays once when scrolled into view; under prefers-reduced-motion
 * it shows the final year with no autoplay or transitions, and offers a year slider instead so
 * the reshuffle stays reachable. */
export function RankRace({ series, worldTotals, expandedCount }: { series: WorldMapTimeSeries; worldTotals: number[]; expandedCount: number }) {
  const reduced = useReducedMotion();
  const model = useMemo(() => buildRaceModel(series), [series]);
  const last = model.years.length - 1;
  const [yearIdx, setYearIdx] = useState(last);
  const [playing, setPlaying] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);
  const autoplayed = useRef(false);

  // Advance one year per tick while playing; stop at the end.
  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setYearIdx((i) => {
        if (i >= last) { setPlaying(false); return last; }
        return i + 1;
      });
    }, YEAR_STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, last]);

  // First time the section scrolls into view, play from the start (never under reduced motion).
  useEffect(() => {
    const el = sectionRef.current;
    if (!el || reduced || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver((entries) => {
      if (autoplayed.current || !entries.some((e) => e.isIntersecting)) return;
      autoplayed.current = true;
      setYearIdx(0);
      setPlaying(true);
    }, { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, [reduced]);

  const frame = raceFrame(model, yearIdx);
  const share = raceShare(frame.topTotal, worldTotals[yearIdx]);
  const ranked = frame.rows.filter((r) => r.inTop).sort((a, b) => a.rank - b.rank);
  const transition = reduced ? 'none' : 'top 450ms ease, opacity 300ms, width 450ms ease';

  const togglePlay = () => {
    if (playing) { setPlaying(false); return; }
    if (yearIdx >= last) setYearIdx(0);
    setPlaying(true);
  };

  return (
    <section ref={sectionRef} aria-labelledby="race-heading" className="landing-race" style={{ padding: 'var(--landing-pad-y) var(--landing-pad-x)', background: 'var(--__s9cmpx-static-background-weak)' }}>
      <div className="landing-race__text" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 id="race-heading" className="landing-h2" style={{ margin: 0 }}>
          {RACE_SIZE} countries{share != null ? `, ${share}% of the world’s CO₂` : ''}
        </h2>
        <p className="__s9cmpx-body1" style={{ margin: 0, color: 'var(--__s9cmpx-static-text-weak)' }}>
          The {RACE_SIZE} largest emitters each year, {model.years[0]} → {model.years[last]}. Watch the ranking reshuffle as the largest growers rise.
        </p>
        {reduced ? (
          <Slider label="Year" min={0} max={last} step={1} value={yearIdx} onChange={setYearIdx} showValue={false} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button type="button" onClick={togglePlay} className="__s9cmpx-button __s9cmpx-button--secondary __s9cmpx-button--m">
              {playing ? 'Pause' : yearIdx >= last ? `Replay ${model.years[0]} → ${model.years[last]}` : 'Play'}
            </button>
          </div>
        )}
        <div aria-hidden="true" style={{ fontSize: 40, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{frame.year}</div>
        <Link to="/overview" style={{ fontWeight: 600, color: 'var(--__s9cmpx-static-text-accent, inherit)' }}>
          Compare any {MAX_SELECTED_COUNTRIES} of {expandedCount} countries on the Overview →
        </Link>
      </div>

      <div className="landing-race__chart" role="group" aria-label={`Ranking race, ${frame.year}`}>
        {/* Screen-reader view: the current year's ranking in rank order (the animated rows below are
            positioned absolutely in name order, so their DOM order says nothing about rank). */}
        <ol style={VISUALLY_HIDDEN} aria-label={`${RACE_SIZE} largest emitters in ${frame.year}, MtCO₂`}>
          {ranked.map((r) => <li key={r.country}>{r.country}: {fmtInt(r.value)}</li>)}
        </ol>
        <div aria-hidden="true" style={{ position: 'relative', height: RACE_SIZE * ROW_PITCH - (ROW_PITCH - ROW_HEIGHT) }}>
          {frame.rows.map((r) => (
            <div
              key={r.country}
              style={{
                position: 'absolute', left: 0, right: 0, top: r.inTop ? r.rank * ROW_PITCH : RACE_SIZE * ROW_PITCH, height: ROW_HEIGHT,
                display: 'flex', alignItems: 'center', gap: 14, opacity: r.inTop ? 1 : 0, pointerEvents: 'none', transition,
              }}
            >
              <div className="__s9cmpx-body2" style={{ width: 'clamp(84px, 22vw, 140px)', flexShrink: 0, textAlign: 'right' }}>{r.country}</div>
              <div style={{ flexGrow: 1, height: '100%', background: 'var(--__s9cmpx-static-background-standard)', borderRadius: '0 4px 4px 0', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${(r.value / model.maxValue) * 100}%`, background: 'var(--__s9cmpx-color-brand-500)', borderRadius: '0 4px 4px 0', transition: reduced ? 'none' : 'width 450ms ease' }} />
              </div>
              <div className="__s9cmpx-body2" style={{ width: 64, flexShrink: 0, fontVariantNumeric: 'tabular-nums' }}>{fmtInt(r.value)}</div>
            </div>
          ))}
        </div>
        <div className="__s9cmpx-body4" style={{ marginTop: 12, color: 'var(--__s9cmpx-static-text-weak)' }}>
          MtCO₂ · bar length on a fixed 0–{fmtInt(model.maxValue)} scale
        </div>
      </div>
    </section>
  );
}
