import { useId, type ReactNode } from 'react';
import { Icon, useReducedMotion } from 'design-system';
import { useCarousel } from '../../hooks/useCarousel';

// The landing's top-of-fold carousel (Area 2, requirements §2.1; ENHANCEMENTS.md decision 59): two banners,
// rate-limited autoplay with an always-visible Pause/Play, a 300 ms crossfade that never moves content.

export interface CarouselSlide {
  id: string;
  /** Short name, used in the tab and the slide's accessible label */
  label: string;
  /** `active` is false while the slide is hidden, so it can hold back its own animation */
  render: (active: boolean) => ReactNode;
}

export const CAROUSEL_STYLES = `
.hero-carousel { display: flex; flex-direction: column; }
.hero-carousel__slides { display: grid; }
.hero-carousel__slide { grid-area: 1 / 1; align-self: center; min-width: 0; transition: opacity 300ms ease, visibility 0s linear 300ms; opacity: 0; visibility: hidden; pointer-events: none; }
.hero-carousel__slide[data-active="true"] { opacity: 1; visibility: visible; pointer-events: auto; transition: opacity 300ms ease, visibility 0s; }
.hero-carousel--static .hero-carousel__slide { transition: none; }
.hero-carousel__controls { order: 2; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 var(--landing-pad-x); padding: 14px 0 0; border-top: 1px solid var(--__s9cmpx-static-divider-weak); }
.hero-carousel__btn { display: inline-flex; align-items: center; justify-content: center; min-width: 36px; height: 36px; padding: 0 12px; border-radius: 4px; cursor: pointer; font: inherit; font-size: 14px; color: inherit; background: transparent; border: 1px solid var(--__s9cmpx-static-divider-standard, currentColor); }
.hero-carousel__btn[aria-current="true"] { background: var(--__s9cmpx-static-background-standard); font-weight: 600; }
.hero-carousel__hint { margin-left: auto; font-size: 13px; color: var(--__s9cmpx-static-text-weak); }
@media (max-width: 640px) { .hero-carousel__hint { display: none; } }
`;

export function HeroCarousel({ slides, ariaLabel = 'Featured' }: { slides: CarouselSlide[]; ariaLabel?: string }) {
  const c = useCarousel({ count: slides.length });
  const reducedMotion = useReducedMotion();
  const uid = useId();

  return (
    <section
      className={`hero-carousel${reducedMotion ? ' hero-carousel--static' : ''}`}
      aria-roledescription="carousel"
      aria-label={ariaLabel}
      {...c.regionHandlers}
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
        <button type="button" className="hero-carousel__btn" onClick={c.autoplay ? c.pause : c.play} aria-label={c.autoplay ? 'Pause automatic rotation' : 'Start automatic rotation'}>
          {c.autoplay ? 'Pause' : 'Play'}
        </button>
        <button type="button" className="hero-carousel__btn" onClick={c.prev} aria-label="Previous slide"><Icon name="chevron-left" size={16} /></button>
        {slides.map((s, i) => (
          <button key={s.id} type="button" className="hero-carousel__btn" aria-current={i === c.index} aria-controls={`${uid}-${s.id}`} onClick={() => c.goTo(i)}>
            <span style={{ fontFamily: 'var(--__s9cmpx-font-families-mono, ui-monospace, monospace)', fontSize: 11, marginRight: 8 }}>{String(i + 1).padStart(2, '0')}</span>
            {s.label}
          </button>
        ))}
        <button type="button" className="hero-carousel__btn" onClick={c.next} aria-label="Next slide"><Icon name="chevron-right" size={16} /></button>
        <span className="hero-carousel__hint">{c.autoplay ? 'Auto-rotating · pauses on hover or focus' : 'Auto-rotate off · ← → when focused'}</span>
      </div>
      <div className="hero-carousel__slides" aria-live={c.autoplay ? 'off' : 'polite'}>
        {slides.map((s, i) => (
          <div key={s.id} id={`${uid}-${s.id}`} className="hero-carousel__slide" role="group" aria-roledescription="slide" aria-label={`${i + 1} of ${slides.length}: ${s.label}`} data-active={i === c.index}
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
