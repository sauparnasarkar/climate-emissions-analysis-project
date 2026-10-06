import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StickyJumpLinks } from './StickyJumpLinks';

const ITEMS = [{ id: 'one', label: 'One', href: '#one' }, { id: 'two', label: 'Two', href: '#two' }];

describe('StickyJumpLinks', () => {
  it('renders the jump links, with the first one current to begin with', () => {
    render(<StickyJumpLinks items={ITEMS} />);
    expect(screen.getByRole('link', { name: 'One' })).toHaveAttribute('aria-current', 'location');
    expect(screen.getByRole('link', { name: 'Two' })).not.toHaveAttribute('aria-current');
  });

  it('offsets jump targets for the pinned row but leaves the shared #main-content landmark on the app-wide offset', () => {
    const { container } = render(<StickyJumpLinks items={ITEMS} />);
    expect(container.querySelector('style')?.textContent).toMatch(/\[id\]:not\(#main-content\) \{ scroll-margin-top: \d+px; \}/);
  });

  it('reports once the row has been measured', () => {
    const onReady = vi.fn();
    render(<StickyJumpLinks items={ITEMS} onReady={onReady} />);
    expect(onReady).toHaveBeenCalled();
  });
});
