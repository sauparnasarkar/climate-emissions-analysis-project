import { act, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useElementHeight } from './useElementHeight';

let trigger: () => void = () => {};
let height = 40;
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { constructor(cb: () => void) { trigger = cb; } observe() {} disconnect() {} });
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => ({ height }) as DOMRect);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function Probe() {
  const [el, setEl] = useState<HTMLElement | null>(null);
  return <div ref={setEl} data-testid="row">{useElementHeight(el)}</div>;
}

describe('useElementHeight', () => {
  it('reports the element\'s height and follows it when it wraps to another line', () => {
    height = 40;
    render(<Probe />);
    expect(screen.getByTestId('row')).toHaveTextContent('40');
    height = 84;
    act(() => trigger());
    expect(screen.getByTestId('row')).toHaveTextContent('84');
  });

  it('is 0 without an element', () => {
    function Empty() { return <span data-testid="e">{useElementHeight(null)}</span>; }
    render(<Empty />);
    expect(screen.getByTestId('e')).toHaveTextContent('0');
  });
});
