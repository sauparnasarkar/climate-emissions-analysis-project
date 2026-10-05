import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { LandingLayout } from './LandingLayout';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

/** matchMedia where only the listed queries match (the design system's width query is '(max-width: 768px)'). */
function stubMedia(matching: (q: string) => boolean) {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: matching(q), media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
}

const mount = () => render(
  <MemoryRouter><Routes><Route element={<LandingLayout theme="analytics" setTheme={() => {}} />}><Route path="/" element={<p>page</p>} /></Route></Routes></MemoryRouter>,
);

describe('LandingLayout header (decision 74)', () => {
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
