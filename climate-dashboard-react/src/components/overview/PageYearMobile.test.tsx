import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PageYearMobile } from './PageYearMobile';

const STOPS = [1970, 1980, 1990, 2000, 2010, 2020, 2024];

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: false, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); document.body.style.overflow = ''; });

const mount = (over: Partial<React.ComponentProps<typeof PageYearMobile>> = {}) => {
  const onSelect = vi.fn();
  const onToggle = vi.fn();
  render(<PageYearMobile stops={STOPS} year={2010} isPlaying={false} onSelect={onSelect} onToggle={onToggle} {...over} />);
  return { onSelect, onToggle, chip: screen.getByRole('button', { name: /^Year 2010/ }) };
};

describe('PageYearMobile', () => {
  it('is a chip showing the page year, which announces that it opens a dialog; no sheet until it is tapped', () => {
    const { chip } = mount();
    expect(chip).toHaveAttribute('aria-haspopup', 'dialog');
    expect(chip).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('marks the chip while the year is playing', () => {
    mount({ isPlaying: true });
    expect(screen.getByLabelText('playing')).toBeInTheDocument();
  });

  it('opens a modal bottom sheet with the decade stops, the current one pressed, and Play; the page behind does not scroll', () => {
    const { chip } = mount();
    fireEvent.click(chip);
    const dialog = screen.getByRole('dialog', { name: 'Page year' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(chip).toHaveAttribute('aria-expanded', 'true');
    const stops = within(dialog).getAllByRole('button', { pressed: undefined }).filter((b) => /^\d{4}$/.test(b.textContent ?? ''));
    expect(stops.map((b) => b.textContent)).toEqual(['1970', '1980', '1990', '2000', '2010', '2020', '2024']);
    expect(within(dialog).getByRole('button', { name: '2010' })).toHaveAttribute('aria-pressed', 'true');
    expect(within(dialog).getByRole('button', { name: '1990' })).toHaveAttribute('aria-pressed', 'false');
    expect(within(dialog).getByRole('button', { name: 'Play' })).toBeInTheDocument();
    expect(document.body.style.overflow).toBe('hidden');
  });

  it('picking a stop reports it, closes the sheet, restores scrolling and returns focus to the chip', () => {
    const { chip, onSelect } = mount();
    fireEvent.click(chip);
    fireEvent.click(screen.getByRole('button', { name: '1980' }));
    expect(onSelect).toHaveBeenCalledWith(1980);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(document.body.style.overflow).toBe('');
    expect(chip).toHaveFocus();
  });

  it('Play (or Pause while playing) toggles the same year animation and closes the sheet', () => {
    const { chip, onToggle } = mount();
    fireEvent.click(chip);
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    cleanup();
    mount({ isPlaying: true });
    fireEvent.click(screen.getByRole('button', { name: /^Year 2010/ }));
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
  });

  it('Escape, the Close button and a tap on the backdrop all close it without changing the year, returning focus to the chip', () => {
    const { chip, onSelect } = mount();
    fireEvent.click(chip);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(chip).toHaveFocus();
    fireEvent.click(chip);
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    fireEvent.click(chip);
    fireEvent.click(document.querySelector('[aria-hidden="true"][style*="rgba(0, 0, 0"]') as HTMLElement);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('moves focus into the sheet and keeps Tab inside it', () => {
    const { chip } = mount();
    fireEvent.click(chip);
    const dialog = screen.getByRole('dialog');
    const buttons = within(dialog).getAllByRole('button');
    expect(buttons[0]).toHaveFocus();
    buttons[buttons.length - 1].focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(buttons[0]).toHaveFocus(); // forward from the last wraps to the first
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(buttons[buttons.length - 1]).toHaveFocus(); // back from the first wraps to the last
  });

  it('renders inside the themed wrapper when there is one, so the sheet takes the theme\'s colours (the variables are defined on that element, not on <body>)', () => {
    render(<div data-theme="analytics" data-testid="themed"><PageYearMobile stops={STOPS} year={2010} isPlaying={false} onSelect={vi.fn()} onToggle={vi.fn()} /></div>);
    fireEvent.click(screen.getByRole('button', { name: /^Year 2010/ }));
    expect(screen.getByTestId('themed').contains(screen.getByRole('dialog'))).toBe(true);
  });

  it('keeps Tab inside the sheet when focus has fallen out of it (playback removed the focused year button)', () => {
    const props = { stops: STOPS, isPlaying: true, onSelect: vi.fn(), onToggle: vi.fn() };
    const { rerender } = render(<PageYearMobile {...props} year={1973} />);
    fireEvent.click(screen.getByRole('button', { name: /^Year 1973/ }));
    const dialog = screen.getByRole('dialog');
    const gone = within(dialog).getByRole('button', { name: '1973' });
    gone.focus();
    rerender(<PageYearMobile {...props} year={1974} />); // 1973 is no longer a listed year; its button is removed
    expect(dialog.contains(document.activeElement)).toBe(false);
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(within(dialog).getAllByRole('button')[0]).toHaveFocus();
  });

  it('pins the body at the current scroll offset while open (iOS does not honour overflow alone) and restores position and scroll on close', () => {
    const scrollTo = vi.fn();
    vi.stubGlobal('scrollTo', scrollTo);
    Object.defineProperty(window, 'scrollY', { value: 640, configurable: true });
    const { chip } = mount();
    fireEvent.click(chip);
    expect(document.body.style.position).toBe('fixed');
    expect(document.body.style.top).toBe('-640px');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(document.body.style.position).toBe('');
    expect(document.body.style.top).toBe('');
    expect(scrollTo).toHaveBeenCalledWith(0, 640);
    Object.defineProperty(window, 'scrollY', { value: 0, configurable: true });
  });

  it('lists a slider-chosen year that is not a stop, so the sheet never shows a stale value', () => {
    render(<PageYearMobile stops={STOPS} year={2013} isPlaying={false} onSelect={vi.fn()} onToggle={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /^Year 2013/ }));
    expect(within(screen.getByRole('dialog')).getByRole('button', { name: '2013' })).toHaveAttribute('aria-pressed', 'true');
  });
});
