import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';
import { LandingLayout } from './LandingLayout';

const realMatchMedia = window.matchMedia;
// Restore only matchMedia: vi.unstubAllGlobals would also drop the shared ResizeObserver stub the other tests rely on.
afterEach(() => { cleanup(); window.matchMedia = realMatchMedia; });

/** matchMedia where only the listed queries match (the design system's width query is '(max-width: 768px)'). */
function stubMedia(matching: (q: string) => boolean) {
  window.matchMedia = ((q: string) => ({ matches: matching(q), media: q, addEventListener: () => {}, removeEventListener: () => {} })) as unknown as typeof window.matchMedia;
}

const mount = () => render(
  <MemoryRouter><Routes><Route element={<LandingLayout theme="analytics" setTheme={() => {}} />}><Route path="/" element={<p>page</p>} /></Route></Routes></MemoryRouter>,
);

describe('LandingLayout header (decision 74)', () => {
  it('survives the phone being rotated from narrow to wide (the hook count must not change)', () => {
    const listeners = new Map<string, (e: { matches: boolean }) => void>();
    const state = { narrow: true };
    window.matchMedia = ((q: string) => ({
      get matches() { return q === '(max-width: 768px)' ? state.narrow : false; },
      media: q,
      addEventListener: (_: string, l: (e: { matches: boolean }) => void) => listeners.set(q, l),
      removeEventListener: () => {},
    })) as unknown as typeof window.matchMedia;
    mount();
    expect(screen.getByRole('button', { name: /menu/i })).toBeInTheDocument();
    state.narrow = false;
    expect(() => act(() => listeners.get('(max-width: 768px)')?.({ matches: false }))).not.toThrow();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
  });

  it('on a desktop-sized screen shows the link row in the header, not a Menu button', () => {
    stubMedia(() => false);
    mount();
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /menu/i })).not.toBeInTheDocument();
  });

  it('on a narrow phone (portrait) shows the Menu button instead of the link row', () => {
    stubMedia((q) => q === '(max-width: 768px)');
    mount();
    expect(screen.getByRole('button', { name: /menu/i })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument(); // the menu's own nav only exists once opened
  });

  it('on a phone turned sideways (wider than 768 px but short) shows the same Menu button, so the links do not wrap to three rows', () => {
    stubMedia((q) => q === '(orientation: landscape) and (max-height: 500px)');
    mount();
    expect(screen.getByRole('button', { name: /menu/i })).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
  });
});
