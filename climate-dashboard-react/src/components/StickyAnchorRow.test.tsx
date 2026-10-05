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
  const rect = (left: number, width: number) => ({ left, width, right: left + width, top: 0, bottom: 0, height: 0, x: left, y: 0, toJSON() {} }) as DOMRect;
  function setup() {
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
    // The row starts at x=100 in the viewport (a year chip sits before it) and is scrolled 50px; link b is at x=600.
    row.getBoundingClientRect = () => rect(100, 300);
    row.scrollLeft = 50;
    const b = document.getElementById('b') as HTMLElement;
    b.getBoundingClientRect = () => rect(600, 100);
    return { row, scrollTo, a: document.getElementById('a')!, b };
  }

  it('centres the current link using its position within the scroller (not offsetLeft, which would include a leading chip)', async () => {
    const { scrollTo, a, b } = setup();
    // A misleading offsetLeft that includes the chip must be ignored.
    Object.defineProperty(b, 'offsetLeft', { value: 9999, configurable: true });
    a.removeAttribute('aria-current');
    b.setAttribute('aria-current', 'location');
    // scrollLeft 50 + (600 - 100) - (300 - 100) / 2 = 450
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith({ left: 450 }));
  });

  it('reveals a current link that is inserted already current (data arriving), not only when the attribute changes', async () => {
    const { row, scrollTo } = setup();
    scrollTo.mockClear();
    const c = document.createElement('a');
    c.setAttribute('aria-current', 'location');
    c.getBoundingClientRect = () => rect(700, 100);
    row.appendChild(c);
    await waitFor(() => expect(scrollTo).toHaveBeenCalled());
  });

  it('reveals the current link when the row is resized into overflow', async () => {
    let fire: () => void = () => {};
    vi.stubGlobal('ResizeObserver', class { constructor(cb: () => void) { fire = cb; } observe() {} disconnect() {} });
    try {
      const { scrollTo } = setup();
      scrollTo.mockClear();
      fire();
      expect(scrollTo).toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
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
