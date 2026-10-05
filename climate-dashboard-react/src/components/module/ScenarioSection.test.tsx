import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse } from '../../api/correlationTypes';
import { PAIR } from '../../test/climateFixtures';
import { SCENARIO_TEMPERATURE } from '../../test/scenarioFixtures';
import { buildScenarioView } from '../../lib/scenarioView';
import { ScenarioSection } from './ScenarioSection';

vi.mock('design-system', async (orig) => ({
  ...(await orig<typeof import('design-system')>()),
  SyChart: (p: { ariaLabel?: string; referenceX?: unknown; series: Array<{ name: string; dashed?: boolean; x: number[] }> }) => (
    <div data-testid="sychart" aria-label={p.ariaLabel} data-ref={JSON.stringify(p.referenceX)} data-series={JSON.stringify(p.series.map((s) => [s.name, !!s.dashed, s.x.length]))} />
  ),
}));
afterEach(cleanup);

const years = Array.from({ length: 12 }, (_, i) => 2013 + i);
const FOSSIL = { ...PAIR, points: years.map((year, i) => ({ year, cumulative_emissions: 1_700_000 + i * 37000, temperature: 1 })) } as unknown as CorrelationEmissionsTemperatureResponse;
const view = (note = true) => buildScenarioView({ ...SCENARIO_TEMPERATURE, reading_note: note ? SCENARIO_TEMPERATURE.reading_note : null } as never, FOSSIL, years.map((y) => ({ year: y, value: 1 + (y - 2013) * 0.05 })), years.slice(4).map((y) => ({ year: y, value: 1.2 })))!;

describe('ScenarioSection', () => {
  it('is titled for the scenario window and labelled illustrative, with the API\'s prescribed wording and its assumptions', () => {
    render(<ScenarioSection view={view()} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Implied temperature by scenario, 2025–2040' })).toBeInTheDocument();
    expect(screen.getByText('Illustrative · implied outcomes, not projections')).toBeInTheDocument();
    expect(screen.getByText(/Implied temperature outcomes · Dependent on the selected regression period/)).toBeInTheDocument();
    expect(screen.getByText(/not formal climate-model projections\./)).toBeInTheDocument();
    expect(screen.getByText(/Slope 0\.520 °C per 1,000 GtCO2 \(Total anthropogenic CO2.*rest of world held at 10\.7% of the global total as of 2024; land-use CO₂ held flat at 4\.7 Gt a year \(2020–2024 mean\)/)).toBeInTheDocument();
  });

  it('draws emissions and implied-temperature charts with the pathways dashed, the start year marked, and the anchor shown', () => {
    render(<ScenarioSection view={view()} />);
    const [emissions, temperature] = screen.getAllByTestId('sychart');
    expect(JSON.parse(emissions.getAttribute('data-series')!).map((s: [string, boolean]) => s.slice(0, 2))).toEqual([['Observed', false], ['Business as usual', true], ['Moderate', true], ['Aggressive', true]]);
    expect(JSON.parse(emissions.getAttribute('data-ref')!)).toEqual({ value: 2025, label: '2025 start' });
    const names = JSON.parse(temperature.getAttribute('data-series')!).map((s: [string]) => s[0]);
    expect(names).toEqual(['Observed (annual)', '5-year mean', 'Business as usual', 'Moderate', 'Aggressive', '1.39 °C anchor']);
    expect(emissions).toHaveAccessibleName(/In 2040: Business as usual 44\.9, Moderate 33\.1, Aggressive 20\.8\./);
    expect(temperature).toHaveAccessibleName(/Anchored at 1\.39 °C in 2024\..*Business as usual 1\.78 °C, Moderate 1\.73 °C, Aggressive 1\.67 °C; the pathways are 0\.11 °C apart\./);
    // the 2040 gap is on the chart: a vertical reference at the horizon, labelled with it
    expect(JSON.parse(temperature.getAttribute('data-ref')!)).toEqual([{ value: 2025, label: '2025 start' }, { value: 2040, label: '0.11 °C apart' }]);
  });

  it('describes only the temperature history that is actually drawn', () => {
    const none = buildScenarioView(SCENARIO_TEMPERATURE, FOSSIL, [], [])!;
    render(<ScenarioSection view={none} />);
    const name = screen.getAllByTestId('sychart')[1].getAttribute('aria-label')!;
    expect(name).not.toMatch(/Observed annual/);
    expect(name).not.toMatch(/5-year mean/);
    expect(name).toMatch(/Anchored at 1\.39 °C in 2024/);
    cleanup();
    const early = buildScenarioView(SCENARIO_TEMPERATURE, FOSSIL, years.slice(0, 5).map((y) => ({ year: y, value: 1 })), [])!; // ends 2017, no mean
    render(<ScenarioSection view={early} />);
    const earlyName = screen.getAllByTestId('sychart')[1].getAttribute('aria-label')!;
    expect(earlyName).toMatch(/Observed annual 2015 to 2017\./);
    expect(earlyName).not.toMatch(/observed .*to 2024/i);
  });

  it('shows the API\'s reading note verbatim, and a 2040 table with a column header for each value', () => {
    render(<ScenarioSection view={view()} />);
    expect(screen.getByText(SCENARIO_TEMPERATURE.reading_note as string)).toBeInTheDocument();
    expect(screen.getByText('Reading note · generated from the output')).toBeInTheDocument();
    const table = screen.getByRole('table');
    expect(within(table).getByRole('columnheader', { name: 'GtCO₂ a year' })).toBeInTheDocument();
    expect(within(within(table).getByRole('row', { name: /Moderate/ })).getAllByRole('cell').map((c) => c.textContent)).toEqual(['33.1', '1.73']);
  });

  it('shows no reading-note card when the API published none, rather than writing one itself', () => {
    render(<ScenarioSection view={view(false)} />);
    expect(screen.queryByText('Reading note · generated from the output')).not.toBeInTheDocument();
  });

  it('states it is not a climate model or projection, in the title chip and the purpose lines', () => {
    render(<ScenarioSection view={view()} />);
    expect(document.body.textContent).not.toMatch(/forecast|will warm|predict/i);
  });
});
