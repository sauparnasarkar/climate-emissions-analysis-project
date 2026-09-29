import { StrictMode, useRef } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { Link, MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRouteAnnouncements } from './useRouteAnnouncements';

function Page() {
  const ref = useRef<HTMLElement>(null);
  useRouteAnnouncements(ref);
  return (
    <>
      <nav>
        <Link to="/about">about</Link>
        <Link to="/overview#pct-change">jump</Link>
        <Link to="/overview#map">jump2</Link>
      </nav>
      <main ref={ref} tabIndex={-1} data-testid="main" />
    </>
  );
}

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><Page /></MemoryRouter>);

let scrollTo: ReturnType<typeof vi.fn>;
beforeEach(() => { scrollTo = vi.fn(); vi.stubGlobal('scrollTo', scrollTo); });
afterEach(() => vi.unstubAllGlobals());

describe('useRouteAnnouncements', () => {
  it('does not steal focus or scroll on the app\'s very first paint', async () => {
    // The first-load flag is module-level state, so use a fresh module for this one.
    vi.resetModules();
    const fresh = await import('./useRouteAnnouncements');
    function FreshPage() {
      const ref = useRef<HTMLElement>(null);
      fresh.useRouteAnnouncements(ref);
      return <main ref={ref} tabIndex={-1} />;
    }
    const focus = vi.spyOn(HTMLElement.prototype, 'focus');
    render(<StrictMode><MemoryRouter><FreshPage /></MemoryRouter></StrictMode>);
    expect(scrollTo).not.toHaveBeenCalled();
    expect(focus).not.toHaveBeenCalled();
    focus.mockRestore();
  });

  it('scrolls to the top and focuses main (without scrolling) on an in-app navigation', () => {
    renderAt('/');
    scrollTo.mockClear(); // a later-mounted layout is not the app's first paint, so mounting itself scrolls
    const focus = vi.spyOn(screen.getByTestId('main'), 'focus');
    fireEvent.click(screen.getByText('about'));
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
  });

  it('leaves scrolling to the jump-to-hash hook when the destination has a #hash', () => {
    renderAt('/');
    scrollTo.mockClear();
    fireEvent.click(screen.getByText('jump'));
    expect(scrollTo).not.toHaveBeenCalled();
  });
});
