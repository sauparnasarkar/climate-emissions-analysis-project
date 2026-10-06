import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CAROUSEL_STYLES, HeroCarousel } from './HeroCarousel';

const SLIDES = [
  { id: 'a', label: 'Climate signal', render: () => <p>First banner</p> },
  { id: 'b', label: 'Emissions', render: () => <p>Second banner</p> },
];

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: false, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

const mount = () => render(<><style>{CAROUSEL_STYLES}</style><HeroCarousel slides={SLIDES} /></>);
const slideEl = (n: number) => document.querySelectorAll('.hero-carousel__slide')[n] as HTMLElement;

describe('HeroCarousel controls (decision 72)', () => {
  it('keeps the Pause/Play button first in tab order, ahead of the moving content and the other controls', () => {
    mount();
    const controls = document.querySelector('.hero-carousel__controls')!;
    expect(controls.firstElementChild).toBe(screen.getByRole('button', { name: /automatic rotation/i }));
    expect(controls.compareDocumentPosition(document.querySelector('.hero-carousel__slides')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('has a dot per banner that keeps its name for assistive technology, marks the current one, and shows a "1 of 2" count (not announced twice)', () => {
    mount();
    const dots = Array.from(document.querySelectorAll('.hero-carousel__btn--dot'));
    expect(dots).toHaveLength(2);
    expect(screen.getByRole('button', { name: /Climate signal/ })).toHaveAttribute('aria-current', 'true');
    expect(screen.getByRole('button', { name: /Emissions/ })).toHaveAttribute('aria-current', 'false');
    const count = document.querySelector('.hero-carousel__count')!;
    expect(count).toHaveTextContent('1 of 2');
    expect(count).toHaveAttribute('aria-hidden', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(count).toHaveTextContent('2 of 2');
  });

  it('floats the controls as a pill pinned to the bottom of the screen on a phone (decision 73), with scroll-padding so focus is never hidden behind it', () => {
    expect(CAROUSEL_STYLES).toMatch(/\.hero-carousel__controls \{ position: sticky; bottom: calc\(12px \+ env\(safe-area-inset-bottom, 0px\)\);[^}]*border-radius: 999px/);
    // the notch/home-indicator inset is part of both the pill's offset and the reserved scroll-padding (viewport-fit=cover is on)
    expect(CAROUSEL_STYLES).toMatch(/scroll-padding-bottom: calc\(84px \+ env\(safe-area-inset-bottom, 0px\)\)/);
    expect(CAROUSEL_STYLES).toMatch(/\.hero-carousel__btn--dot\[aria-current="true"\]::before \{ width: 32px/);
    // every dot keeps a 44 px target (only the drawn dot is small), not just the active one
    expect(CAROUSEL_STYLES).toMatch(/\.hero-carousel__btn--dot \{ min-width: 44px; position: relative; \}/);
    expect(CAROUSEL_STYLES).not.toMatch(/min-width: 28px/);
  });

  it('the pill is frosted glass (decision 80): a translucent tint with a backdrop blur, guarded by @supports, with opaque fallbacks', () => {
    const css = CAROUSEL_STYLES;
    expect(css).toMatch(/@supports \(\(-webkit-backdrop-filter: blur\(1px\)\) or \(backdrop-filter: blur\(1px\)\)\) and \(background: color-mix/);
    expect(css).toMatch(/background: color-mix\(in srgb, var\(--__s9cmpx-static-background-standard\) 80%, transparent\)/);
    expect(css).toMatch(/backdrop-filter: blur\(14px\) saturate\(1\.5\)/);
    // The plain rule stays opaque (fallback where the glass is unsupported)...
    expect(css).toMatch(/\.hero-carousel__controls \{ position: sticky;[^}]*background: var\(--__s9cmpx-static-background-standard\);/);
    // ...and a reduced-transparency preference turns the glass off.
    expect(css).toMatch(/@media \(prefers-reduced-transparency: reduce\)[\s\S]*backdrop-filter: none !important/);
  });

  it('carries the phone layout: one non-wrapping row of 44px targets, and only the showing/leaving slide takes room', () => {
    mount();
    expect(CAROUSEL_STYLES).toMatch(/@media \(max-width: 1100px\), \(max-width: 1440px\) and \(pointer: coarse\)/);
    expect(CAROUSEL_STYLES).toMatch(/flex-wrap: nowrap/);
    expect(CAROUSEL_STYLES).toMatch(/min-width: 44px; height: 44px/);
    expect(CAROUSEL_STYLES).toMatch(/\.hero-carousel__slide\[data-motion="hidden"\] \{ display: none; \}/);
  });
});

describe('HeroCarousel leaving slide', () => {
  it('under reduced motion the previous slide is hidden at once, with no 520 ms wait', () => {
    window.matchMedia = ((q: string) => ({ matches: q === '(prefers-reduced-motion: reduce)', media: q, addEventListener: () => {}, removeEventListener: () => {} })) as unknown as typeof window.matchMedia;
    mount();
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(slideEl(0)).toHaveAttribute('data-motion', 'hidden');
    expect(slideEl(1)).toHaveAttribute('data-motion', 'enter-forward');
  });


  it('keeps the leaving slide in its exit state while it moves out, then marks it plainly hidden', () => {
    mount();
    expect(slideEl(1)).toHaveAttribute('data-motion', 'hidden');
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(slideEl(0)).toHaveAttribute('data-motion', 'exit-forward');
    expect(slideEl(1)).toHaveAttribute('data-motion', 'enter-forward');
    act(() => { vi.advanceTimersByTime(600); });
    expect(slideEl(0)).toHaveAttribute('data-motion', 'hidden');
    expect(slideEl(1)).toHaveAttribute('data-motion', 'enter-forward');
  });

  it('does it again on a later move back to a slide it has already shown', () => {
    mount();
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    act(() => { vi.advanceTimersByTime(600); });
    fireEvent.click(screen.getByRole('button', { name: 'Previous slide' }));
    expect(slideEl(1)).toHaveAttribute('data-motion', 'exit-back');
    act(() => { vi.advanceTimersByTime(600); });
    expect(slideEl(1)).toHaveAttribute('data-motion', 'hidden');
    fireEvent.click(screen.getByRole('button', { name: 'Next slide' }));
    expect(slideEl(0)).toHaveAttribute('data-motion', 'exit-forward'); // not left "hidden" by the earlier settle
    expect(within(slideEl(1)).getByText('Second banner')).toBeInTheDocument();
  });
});
