import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PageYearControl } from './PageYearControl';

const STOPS = [1970, 1980, 1990, 2000, 2010, 2020, 2024];

describe('PageYearControl', () => {
  it('offers the decade stops and shows the page year', () => {
    render(<PageYearControl stops={STOPS} year={2010} isPlaying={false} onSelect={vi.fn()} onToggle={vi.fn()} />);
    const group = screen.getByRole('group', { name: 'Page year' });
    const combo = within(group).getByRole('combobox', { name: 'Page year' });
    expect(combo).toHaveTextContent('2010');
    fireEvent.click(combo);
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['1970', '1980', '1990', '2000', '2010', '2020', '2024']);
  });

  it('lists a slider-chosen year that is not a stop, so the select never shows a stale value', () => {
    render(<PageYearControl stops={STOPS} year={2013} isPlaying={false} onSelect={vi.fn()} onToggle={vi.fn()} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Page year' }));
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['1970', '1980', '1990', '2000', '2010', '2013', '2020', '2024']);
  });

  it('reports the chosen year as a number, and Play/Pause toggles', () => {
    const onSelect = vi.fn();
    const onToggle = vi.fn();
    const { rerender } = render(<PageYearControl stops={STOPS} year={2024} isPlaying={false} onSelect={onSelect} onToggle={onToggle} />);
    fireEvent.click(screen.getByRole('combobox', { name: 'Page year' }));
    fireEvent.click(screen.getByRole('option', { name: '1980' }));
    expect(onSelect).toHaveBeenCalledWith(1980);
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    rerender(<PageYearControl stops={STOPS} year={2024} isPlaying onSelect={onSelect} onToggle={onToggle} />);
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });
});
