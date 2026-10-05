import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AnchorScroll, STICKY_HEADER_PX, StickyAnchorRow } from './StickyAnchorRow';

describe('StickyAnchorRow', () => {
  it('is pinned below the app header and carries the phone layout (one scrolling line, hidden scrollbar) in its styles', () => {
    render(<StickyAnchorRow innerRef={() => {}}><span>row</span></StickyAnchorRow>);
    const row = screen.getByText('row').closest('[style*="position: sticky"]') as HTMLElement;
    expect(row.style.top).toBe(`${STICKY_HEADER_PX}px`);
    const css = row.querySelector('style')!.textContent!;
    expect(css).toMatch(/max-width: 640px/);
    expect(css).toMatch(/flex-wrap: nowrap/);
    expect(css).toMatch(/overflow-x: auto/);
    expect(css).toMatch(/scrollbar-width: none/);
  });
  it('gives its element back to the page to measure', () => {
    const ref = vi.fn();
    render(<StickyAnchorRow innerRef={ref}>x</StickyAnchorRow>);
    expect(ref).toHaveBeenCalledWith(expect.any(HTMLDivElement));
  });
});

describe('AnchorScroll', () => {
  it('scrolls the row (never the page) to centre the current link when it changes and the row overflows', async () => {
    render(
      <AnchorScroll>
        <a id="a" href="#a" aria-current="location">First</a>
        <a id="b" href="#b">Second</a>
      </AnchorScroll>,
    );
    const row = document.querySelector('.area2-anchor-scroll') as HTMLElement;
    const scrollTo = vi.fn();
    row.scrollTo = scrollTo as never;
    Object.defineProperty(row, 'scrollWidth', { value: 800, configurable: true });
    Object.defineProperty(row, 'clientWidth', { value: 300, configurable: true });
    const b = document.getElementById('b') as HTMLElement;
    Object.defineProperty(b, 'offsetLeft', { value: 500, configurable: true });
    Object.defineProperty(b, 'offsetWidth', { value: 100, configurable: true });
    document.getElementById('a')!.removeAttribute('aria-current');
    b.setAttribute('aria-current', 'location');
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ left: 400 })); // 500 - (300 - 100) / 2
  });
  it('does nothing when the row does not overflow', async () => {
    render(<AnchorScroll><a id="a" href="#a" aria-current="location">Only</a></AnchorScroll>);
    const row = document.querySelector('.area2-anchor-scroll') as HTMLElement;
    const scrollTo = vi.fn();
    row.scrollTo = scrollTo as never;
    document.getElementById('a')!.removeAttribute('aria-current');
    document.getElementById('a')!.setAttribute('aria-current', 'location');
    await new Promise((r) => setTimeout(r, 20));
    expect(scrollTo).not.toHaveBeenCalled();
  });
});
