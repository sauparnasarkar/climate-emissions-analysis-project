import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Button, useReducedMotion } from 'design-system';

interface Props {
  stops: number[];
  year: number;
  isPlaying: boolean;
  onSelect: (year: number) => void;
  onToggle: () => void;
}

/**
 * The page year on a phone (ENHANCEMENTS.md decisions 64 and 69): a chip that opens a bottom sheet with the decade stops and Play/Pause. A modal dialog:
 * focus moves in and returns to the chip, Tab stays inside, Escape and a tap on the backdrop close it, and the page does not scroll behind it. Picking a stop
 * or pressing Play closes the sheet so the change is seen on the page. It sets the same year value as the desktop select and the map's controls.
 */
export function PageYearMobile({ stops, year, isPlaying, onSelect, onToggle }: Props) {
  const [open, setOpen] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const years = stops.includes(year) ? stops : [...stops, year].sort((a, b) => a - b);

  const close = () => {
    setOpen(false);
    chipRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const sheet = sheetRef.current;
    const focusables = () => Array.from(sheet?.querySelectorAll<HTMLElement>('button:not([disabled])') ?? []);
    focusables()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        chipRef.current?.focus();
        return;
      }
      if (e.key !== 'Tab') return;
      const f = focusables();
      if (f.length === 0) return;
      const first = f[0];
      const last = f[f.length - 1];
      // Focus can fall outside the sheet (e.g. playback replaced the focused year's button): bring Tab back in rather than into the page behind.
      if (!sheet?.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? last : first).focus(); return; }
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <>
      <button
        ref={chipRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className="__s9cmpx-label3"
        style={{ flex: 'none', display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 16, cursor: 'pointer', border: '1px solid var(--__s9cmpx-static-divider-standard)', background: 'var(--__s9cmpx-static-background-standard)', color: 'var(--__s9cmpx-static-text-standard)', fontVariantNumeric: 'tabular-nums' }}
      >
        <span>Year {year}</span>
        {isPlaying && <span aria-label="playing" style={{ fontSize: 10 }}>▶</span>}
        <span aria-hidden="true">▾</span>
      </button>
      {open &&
        createPortal(
          <div style={{ position: 'fixed', inset: 0, zIndex: 100 }}>
            <div aria-hidden="true" onClick={close} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.45)' }} />
            <div
              ref={sheetRef}
              role="dialog"
              aria-modal="true"
              aria-label="Page year"
              style={{
                position: 'absolute', left: 0, right: 0, bottom: 0, padding: '16px 16px calc(16px + env(safe-area-inset-bottom, 0px))',
                borderRadius: '16px 16px 0 0', background: 'var(--__s9cmpx-static-background-standard)', color: 'var(--__s9cmpx-static-text-standard)', boxShadow: '0 -4px 24px rgba(0,0,0,0.35)',
                animation: reduceMotion ? 'none' : 'area2-sheet-in 180ms ease-out',
              }}
            >
              <style>{'@keyframes area2-sheet-in { from { transform: translateY(24px); opacity: 0; } to { transform: none; opacity: 1; } }'}</style>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <span className="__s9cmpx-label2">Year</span>
                <Button variant="ghost-blue" onClick={close}>Close</Button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8, marginBottom: 12 }}>
                {years.map((y) => (
                  <button
                    key={y}
                    type="button"
                    aria-pressed={y === year}
                    onClick={() => { onSelect(y); setOpen(false); chipRef.current?.focus(); }}
                    className="__s9cmpx-label3"
                    // The current stop is marked by a heavier border, bold weight and a stronger surface in the standard text colour -- not by a coloured fill, whose white
                    // text falls below AA on the dark theme's primary colour (and colour alone is not a state cue).
                    style={{ padding: '10px 0', borderRadius: 8, cursor: 'pointer', fontVariantNumeric: 'tabular-nums', color: 'var(--__s9cmpx-static-text-standard)', border: y === year ? '2px solid var(--__s9cmpx-interactive-fill-primary-default)' : '1px solid var(--__s9cmpx-static-divider-standard)', background: y === year ? 'var(--__s9cmpx-static-background-strong)' : 'transparent', fontWeight: y === year ? 700 : 400 }}
                  >
                    {y}
                  </button>
                ))}
              </div>
              <Button variant="primary" onClick={() => { onToggle(); setOpen(false); chipRef.current?.focus(); }}>{isPlaying ? 'Pause' : 'Play'}</Button>
            </div>
          </div>,
          // Into the themed wrapper (the theme's variables live on its [data-theme] element, not on <body>), so the sheet is dark in the dark theme.
          chipRef.current?.closest('[data-theme]') ?? document.body,
        )}
    </>
  );
}
