import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { CONCENTRATION, PAIR, TEMPERATURE } from '../../test/climateFixtures';
import { buildClimateSignal } from '../../lib/climateSignal';
import { buildHeadline } from '../../lib/headline';
import { Ar6Strip } from './Ar6Strip';
import { CausalChain } from './CausalChain';
import { HeadlineRelationship } from './HeadlineRelationship';

const signal = buildClimateSignal(PAIR, TEMPERATURE, CONCENTRATION)!;

describe('CausalChain', () => {
  it('shows four cells in order, with the forcing cell marked as a concept and carrying no number', () => {
    render(<CausalChain signal={signal} emissions={{ year: 2024, total: 37398.067 }} />);
    const cells = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(cells).toHaveLength(4);
    expect(cells[0]).toHaveTextContent('1 · Emissions');
    expect(cells[0]).toHaveTextContent('37,398 MtCO₂ in 2024');
    expect(cells[1]).toHaveTextContent('2 · Concentration');
    expect(cells[1]).toHaveTextContent('424.6 ppm in 2024');
    expect(cells[1]).toHaveTextContent('287 ppm in 1850');
    expect(cells[2]).toHaveTextContent('3 · Radiative forcing · concept');
    expect(cells[2]).toHaveTextContent('Not calculated here.');
    expect(cells[2].textContent).not.toMatch(/\d{2}/);
    expect(cells[3]).toHaveTextContent('4 · Temperature anomaly');
    expect(cells[3]).toHaveTextContent('+1.62 °C in 2024');
  });

  it('says nothing for the emissions figure rather than a zero when it is unavailable', () => {
    render(<CausalChain signal={signal} emissions={null} />);
    const first = within(screen.getByRole('list')).getAllByRole('listitem')[0];
    expect(first.textContent).not.toMatch(/MtCO₂/);
    expect(first).toHaveTextContent('stock that stays');
  });
});

describe('Ar6Strip', () => {
  it('describes where the slopes sit against the AR6 range, in words for assistive tech', () => {
    render(<Ar6Strip slope={0.52} fossilSlope={0.797} />);
    const svg = screen.getByRole('img');
    expect(svg).toHaveAccessibleName(/AR6 very likely range is 0\.27 to 0\.63, best estimate 0\.45.*slope is 0\.520.*fossil and cement only slope is 0\.797/);
    expect(screen.getByText(/IPCC AR6 very likely range 0\.27–0\.63/)).toBeInTheDocument();
  });
  it('leaves out the fossil marker when there is none', () => {
    render(<Ar6Strip slope={0.52} fossilSlope={null} />);
    expect(screen.getByRole('img')).not.toHaveAccessibleName(/fossil/);
    expect(screen.queryByText(/Fossil \+ cement only/)).not.toBeInTheDocument();
  });
});

describe('HeadlineRelationship', () => {
  const headline = buildHeadline(signal, { ...PAIR, fit: { ...PAIR.fit, slope: 0.797 } } as never);
  const mount = (s = signal) => render(<MemoryRouter><HeadlineRelationship signal={s} headline={buildHeadline(s, { ...PAIR, fit: { ...PAIR.fit, slope: 0.797 } } as never)} /></MemoryRouter>);

  it('shows the slope, interval, fit quality, window and the labelled fossil-only comparison, all from the API figures', () => {
    mount();
    expect(screen.getByRole('heading', { level: 2, name: 'Global relationship' })).toBeInTheDocument();
    expect(screen.getByText('Warming per 1,000 GtCO₂')).toBeInTheDocument();
    expect(screen.getByText('Warming per 1,000 GtCO₂').parentElement).toHaveTextContent('0.520 °C'); // the big figure (the AR6 strip repeats it)
    expect(screen.getByText('0.480–0.559')).toBeInTheDocument();
    expect(screen.getByText('0.90')).toBeInTheDocument(); // R² from the response, not a typed-in figure
    expect(screen.getByText('1850–2024 (175)')).toBeInTheDocument();
    expect(screen.getByText('Fossil + cement only')).toBeInTheDocument();
    expect(screen.getAllByText('0.797').length).toBeGreaterThan(0);
    expect(headline.slope).toBeCloseTo(0.5196);
  });

  it('is descriptive: correlation not cause, not a climate model, and the baseline card states reference, formula, range and exclusions', () => {
    mount();
    expect(screen.getByText(/not as proof of cause/)).toBeInTheDocument();
    expect(screen.getByText(/not a climate model/i)).toBeInTheDocument();
    expect(screen.getByText('1850–1900 mean')).toBeInTheDocument();
    expect(screen.getByText('ΔT = T − mean(T₁₈₅₀–₁₉₀₀)')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument(); // no excluded years
  });

  it('shows the Berkeley Earth vintage caveat while it is unreconciled, and lists excluded years', () => {
    mount({ ...signal, vintageCaveat: 'Based on Berkeley Earth file vintage 2025-01-10.', omittedYears: [1900, 1901] });
    expect(screen.getByRole('note')).toHaveTextContent('Berkeley Earth file vintage 2025-01-10');
    expect(screen.getByText('1900, 1901')).toBeInTheDocument();
  });

  it('omits R² and the fossil comparison when the data lacks them rather than showing blanks', () => {
    const noFossil = buildHeadline({ ...signal, fit: { ...signal.fit, rSquared: null } }, null);
    render(<MemoryRouter><HeadlineRelationship signal={signal} headline={noFossil} /></MemoryRouter>);
    expect(screen.queryByText('R²')).not.toBeInTheDocument();
    expect(screen.queryByText('Fossil + cement only')).not.toBeInTheDocument();
  });
});
