import { useEffect, useId, useLayoutEffect, useState, type ReactNode } from 'react';
import { Icon, useReducedMotion } from 'design-system';
import { useCarousel } from '../../hooks/useCarousel';

// The landing's top-of-fold carousel (Area 2, requirements §2.1; ENHANCEMENTS.md decision 59): two banners,
// auto-rotate controlled only by an always-visible Pause/Play button; slides slide in and out sideways (no motion under reduced-motion settings).

export interface CarouselSlide {
  id: string;
  /** Short name, used in the tab and the slide's accessible label */
  label: string;
  /** `active` is false while the slide is hidden, so it can hold back its own animation */
  render: (active: boolean) => ReactNode;
}

export const CAROUSEL_STYLES = `
.hero-carousel { display: flex; flex-direction: column; }
.hero-carousel__slides { display: grid; overflow: hidden; }
/* Slides slide sideways. The one coming in and the one going out are animated by keyframes (not parked positions), so the
   direction follows the move itself: forward -- Next, auto-rotate, also from the last slide round to the first -- brings the new
   slide in from the right and sends the old one out to the left; back reverses it. */
.hero-carousel__slide { grid-area: 1 / 1; align-self: center; min-width: 0; opacity: 0; visibility: hidden; pointer-events: none; }
.hero-carousel__slide[data-motion="rest"] { opacity: 1; visibility: visible; pointer-events: auto; }
.hero-carousel__slide[data-motion="enter-forward"] { visibility: visible; pointer-events: auto; animation: hero-slide-in-from-right 500ms cubic-bezier(.4, 0, .2, 1) both; }
.hero-carousel__slide[data-motion="enter-back"] { visibility: visible; pointer-events: auto; animation: hero-slide-in-from-left 500ms cubic-bezier(.4, 0, .2, 1) both; }
.hero-carousel__slide[data-motion="exit-forward"] { animation: hero-slide-out-to-left 500ms cubic-bezier(.4, 0, .2, 1) both; }
.hero-carousel__slide[data-motion="exit-back"] { animation: hero-slide-out-to-right 500ms cubic-bezier(.4, 0, .2, 1) both; }
@keyframes hero-slide-in-from-right { from { transform: translateX(100%); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes hero-slide-in-from-left { from { transform: translateX(-100%); opacity: 0; } to { transform: none; opacity: 1; } }
@keyframes hero-slide-out-to-left { from { transform: none; opacity: 1; visibility: visible; } to { transform: translateX(-100%); opacity: 0; visibility: hidden; } }
@keyframes hero-slide-out-to-right { from { transform: none; opacity: 1; visibility: visible; } to { transform: translateX(100%); opacity: 0; visibility: hidden; } }
/* No movement under reduced motion: the slide that is leaving is simply gone and the new one is there. */
.hero-carousel--static .hero-carousel__slide { animation: none !important; }
.hero-carousel--static .hero-carousel__slide[data-motion^="enter"] { opacity: 1; }
.hero-carousel--static .hero-carousel__slide[data-motion^="exit"] { visibility: hidden; opacity: 0; }
.hero-carousel__controls { order: 2; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 var(--landing-pad-x); padding: 10px 0 12px; border-top: 1px solid var(--__s9cmpx-static-divider-weak); }
.hero-carousel__btn { display: inline-flex; align-items: center; justify-content: center; min-width: 36px; height: 36px; padding: 0 12px; border-radius: 4px; cursor: pointer; font: inherit; font-size: 14px; color: inherit; background: transparent; border: 1px solid var(--__s9cmpx-static-divider-standard, currentColor); }
.hero-carousel__btn[aria-current="true"] { background: var(--__s9cmpx-static-background-standard); font-weight: 600; }
.hero-carousel__hint { margin-left: auto; font-size: 13px; color: var(--__s9cmpx-static-text-weak); }
/* Phones (decision 72): one compact row -- previous, Pause/Play, a dot per banner, "1 of 2", next -- instead of wrapped labelled buttons. */
.hero-carousel__count { display: none; }
@media (max-width: 1100px), (max-width: 1440px) and (pointer: coarse) {
  .hero-carousel__hint { display: none; }
  /* Decision 79: room under each banner for the pill (54 px + gap), which docks into it at rest instead of sitting below it, so at rest it covers nothing. */
  .hero-carousel__slides { padding-bottom: calc(72px + env(safe-area-inset-bottom, 0px)); }
  /* The slides are stacked in one grid cell, so the tallest would set the height and leave a gap above the controls under a shorter banner: on a phone only the showing (and, during the move, the leaving) slide takes room. */
  .hero-carousel__slide[data-motion="hidden"] { display: none; }
  /* Decision 73: a pill pinned to the bottom of the screen while the carousel is on view (it docks at the carousel's own end), so the controls are seen
     without scrolling -- like the pagination pill on the Fitch Ratings mobile hero. Page scroll-padding keeps a focused element from sitting behind it. */
  .hero-carousel__controls { position: sticky; bottom: calc(12px + env(safe-area-inset-bottom, 0px)); z-index: 6; align-self: center; width: fit-content; max-width: calc(100% - 24px); margin: calc(-66px - env(safe-area-inset-bottom, 0px)) 12px 0; flex-wrap: nowrap; justify-content: center; gap: 2px; padding: 4px 8px; border: 1px solid var(--__s9cmpx-static-divider-standard, #8896a8); border-radius: 999px; background: var(--__s9cmpx-static-background-standard); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35); }
  html:has(.hero-carousel__controls) { scroll-padding-bottom: calc(84px + env(safe-area-inset-bottom, 0px)); }
  .hero-carousel__btn { min-width: 44px; height: 44px; padding: 0; }
  .hero-carousel__btn--playpause { padding: 0 12px; }
  .hero-carousel__btn--prev { order: 1; margin-right: auto; }
  .hero-carousel__btn--playpause { order: 2; }
  .hero-carousel__btn--dot { order: 3; background: none; border: 0; }
  .hero-carousel__count { order: 4; display: inline; font-size: 13px; color: var(--__s9cmpx-static-text-weak); margin: 0 6px; }
  .hero-carousel__btn--next { order: 5; margin-left: auto; }
  .hero-carousel__btn--dot .hero-carousel__num, .hero-carousel__btn--dot .hero-carousel__label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
  .hero-carousel__btn--dot { min-width: 44px; position: relative; } /* the target stays 44 px; only the drawn dot is small */
  .hero-carousel__btn--dot::before { content: ""; display: block; width: 12px; height: 12px; border-radius: 6px; border: 2px solid var(--__s9cmpx-static-text-standard); box-sizing: border-box; }
  .hero-carousel__btn--dot[aria-current="true"]::before { width: 32px; border-color: var(--__s9cmpx-interactive-fill-primary-default); background: var(--__s9cmpx-interactive-fill-primary-default); }
}
`;

export function HeroCarousel({ slides, ariaLabel = 'Featured' }: { slides: CarouselSlide[]; ariaLabel?: string }) {
  const c = useCarousel({ count: slides.length });
  const reducedMotion = useReducedMotion();
  const uid = useId();
  // The first slide is simply there; after a move, the new one enters and the old one leaves, each in the move's direction.
  // The leaving slide only needs its state while its exit runs; after that it is plainly hidden (on a phone that frees its room).
  // `settled` is reset before paint on every move, so the leaving slide never shows a frame of "hidden" before its exit starts.
  const [settled, setSettled] = useState(false);
  useLayoutEffect(() => setSettled(false), [c.index]);
  useEffect(() => {
    if (c.previous === null) return;
    const t = window.setTimeout(() => setSettled(true), 520);
    return () => window.clearTimeout(t);
  }, [c.index, c.previous]);
  // Under reduced motion there is no exit to wait for, so the previous slide is settled at once (no delayed height change on a phone).
  const leaving = settled || reducedMotion ? null : c.previous;
  const motionOf = (i: number) => (i === c.index ? (c.previous === null ? 'rest' : `enter-${c.direction}`) : i === leaving ? `exit-${c.direction}` : 'hidden');

  return (
    <section
      className={`hero-carousel${reducedMotion ? ' hero-carousel--static' : ''}`}
      aria-roledescription="carousel"
      aria-label={ariaLabel}
      onKeyDown={(e) => {
        // ←/→ switch slides only from the carousel's own controls (or the region itself). A key pressed inside a slide --
        // the hero's Year slider, say -- keeps its own meaning, and an event something else already handled is left alone.
        if (e.defaultPrevented) return;
        const target = e.target as HTMLElement;
        if (target !== e.currentTarget && !target.closest('.hero-carousel__controls')) return;
        if (e.key === 'ArrowRight') { e.preventDefault(); c.next(); }
        else if (e.key === 'ArrowLeft') { e.preventDefault(); c.prev(); }
      }}
    >
      {/* First in the DOM (so first in tab order) but drawn below the slides (CSS `order`): the pause control
          must be reachable before the moving content. */}
      <div className="hero-carousel__controls">
        <button type="button" className="hero-carousel__btn hero-carousel__btn--playpause" onClick={c.autoplay ? c.pause : c.play} aria-label={c.autoplay ? 'Pause automatic rotation' : 'Start automatic rotation'}>
          {c.autoplay ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="hero-carousel__btn hero-carousel__btn--prev" onClick={c.prev} aria-label="Previous slide"><Icon name="chevron-left" size={16} /></button>
        {slides.map((s, i) => (
          <button key={s.id} type="button" className="hero-carousel__btn hero-carousel__btn--dot" aria-current={i === c.index} aria-controls={`${uid}-${s.id}`} onClick={() => c.goTo(i)}>
            <span className="hero-carousel__num" style={{ fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)', fontSize: 11, marginRight: 8 }}>{String(i + 1).padStart(2, '0')}</span>
            <span className="hero-carousel__label">{s.label}</span>
          </button>
        ))}
        <button type="button" className="hero-carousel__btn hero-carousel__btn--next" onClick={c.next} aria-label="Next slide"><Icon name="chevron-right" size={16} /></button>
        <span className="hero-carousel__count" aria-hidden="true">{c.index + 1} of {slides.length}</span>
        <span className="hero-carousel__hint">{c.autoplay ? 'Auto-rotating · use Pause to stop' : 'Auto-rotate off · ← → to switch'}</span>
      </div>
      <div className="hero-carousel__slides" aria-live={c.autoplay ? 'off' : 'polite'}>
        {slides.map((s, i) => (
          <div key={s.id} id={`${uid}-${s.id}`} className="hero-carousel__slide" role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${slides.length}: ${s.label}`} data-active={i === c.index} data-motion={motionOf(i)}
            // Hidden slides are also removed from the accessibility tree and made inert (CSS `visibility` alone would do the
            // same in a browser; this states it explicitly so focus and assistive tech can never reach a slide that isn't showing).
            aria-hidden={i !== c.index} inert={i !== c.index}>
            {s.render(i === c.index)}
          </div>
        ))}
      </div>
    </section>
  );
}
