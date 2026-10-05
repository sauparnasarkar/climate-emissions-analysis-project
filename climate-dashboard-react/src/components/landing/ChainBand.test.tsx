import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import type { ClimateSignal } from '../../lib/climateSignal';
import { ChainBand } from './ChainBand';

const SIGNAL: ClimateSignal = {
  points: [], fit: { slope: 0.52, ciLow: 0.48, ciHigh: 0.56, rSquared: 0.9, unit: 'u', start: 1850, end: 2024, nYears: 175 }, line: { x0: 0, y0: 0, x1: 1, y1: 1 },
  temperature: { value: 1.617, year: 2024 }, concentration: { value: 424.6, year: 2024 },
  series: { concentration: [{ year: 1850, value: 286.8 }, { year: 1959, value: 315.9 }, { year: 2024, value: 424.6 }], temperature: [{ year: 2023, value: 1.5 }, { year: 2024, value: 1.617 }] },
  spliceYear: 1959, ppm1850: 286.8, omittedYears: [], vintageCaveat: 'Based on Berkeley Earth file vintage 2025-01-10; a possible ~0.1 °C discrepancy is not yet reconciled.',
};
const EMISSIONS = { year: 2024, total: 37398.067, series: [{ year: 1970, value: 14000 }, { year: 2024, value: 37398 }] };

function renderBand(signal: ClimateSignal = SIGNAL) {
  return render(<MemoryRouter><ChainBand signal={signal} emissions={EMISSIONS} /></MemoryRouter>);
}

describe('ChainBand', () => {
  it('is an ordered list of the four steps, labelled by its heading, in the order of the causal chain', () => {
    renderBand();
    const section = screen.getByRole('region', { name: 'The chain reaction, step by step' });
    const steps = within(section).getByRole('list').querySelectorAll(':scope > li:not([aria-hidden="true"])');
    expect(section.querySelector('ol')).not.toBeNull();
    expect([...steps].map((li) => li.querySelector('.chain-band__label')?.textContent)).toEqual(['01 · Emissions', '02 · Concentration', '03 · Radiative forcing · concept only', '04 · Temperature anomaly']);
  });

  it('shows global accumulated totals from the data, each figure with its own year, and no same-year claim', () => {
    renderBand();
    expect(screen.getByText('37,398')).toBeInTheDocument();
    expect(screen.getByText('Released worldwide in 2024. Each year adds to the total already in the air.')).toBeInTheDocument();
    expect(screen.getByText('424.6')).toBeInTheDocument();
    expect(screen.getByText('CO₂ in the air, 2024. Up 48% on 1850.')).toBeInTheDocument(); // 424.6 / 286.8 = 1.48
    expect(screen.getByText('+1.62 °C')).toBeInTheDocument();
    expect(screen.getByText('2024, above the 1850–1900 average.')).toBeInTheDocument();
    expect(screen.getByText(/One country’s emissions in one year do not set that year’s temperature/)).toBeInTheDocument();
  });

  it('states the ice-core / Mauna Loa splice and carries the unreconciled-vintage caveat', () => {
    renderBand();
    expect(screen.getByText('Ice core to 1958 · Mauna Loa from 1959')).toBeInTheDocument();
    expect(screen.getByText(/^Based on Berkeley Earth file vintage 2025-01-10/)).toBeInTheDocument();
  });

  it('keeps radiative forcing copy-only: no number, no chart', () => {
    renderBand();
    const forcing = screen.getByText('03 · Radiative forcing · concept only').closest('li')!;
    expect(within(forcing).getByText('Explained, not measured')).toBeInTheDocument();
    expect(within(forcing).getByText(/described here, not calculated: the platform holds no forcing dataset/)).toBeInTheDocument();
    expect(forcing.querySelector('svg')).toBeNull();
    expect(forcing.textContent?.replace('03 ', '')).not.toMatch(/\d/); // apart from its "03" label, no figure at all
  });

  it('hides the decorative arrows and sparklines from assistive technology and links to the module and the Overview', () => {
    const { container } = renderBand();
    expect(container.querySelectorAll('li[aria-hidden="true"]')).toHaveLength(3);
    container.querySelectorAll('svg').forEach((svg) => expect(svg).toHaveAttribute('aria-hidden', 'true'));
    expect(screen.getByRole('link', { name: 'Open the Correlation module →' })).toHaveAttribute('href', '/climate-correlation');
    expect(screen.getByRole('link', { name: 'See on the Overview →' })).toHaveAttribute('href', '/overview');
  });

  it('omits "up x% on 1850", the splice note and the caveat when the API did not supply them', () => {
    renderBand({ ...SIGNAL, ppm1850: null, spliceYear: null, vintageCaveat: null });
    expect(screen.getByText('CO₂ in the air, 2024.')).toBeInTheDocument();
    expect(screen.queryByText(/Ice core to/)).not.toBeInTheDocument();
    expect(screen.getByText('Berkeley Earth')).toBeInTheDocument();
  });
});
