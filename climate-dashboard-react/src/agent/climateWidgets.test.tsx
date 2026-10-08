import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import { ALL_GAS_PAIR, COMPOSITION, CONCENTRATION, HEADLINE_PAIR, META, TEMPERATURE, TEMPERATURE_MEAN5Y } from '../test/climateFixtures';
import { SCENARIO_TEMPERATURE } from '../test/scenarioFixtures';
import { shareResponse } from '../test/shareFixtures';
import { WidgetRenderer } from './WidgetRenderer';
import { singleYearRows, sourceRows } from './climateRows';
import type { WidgetSpec } from './types';

vi.mock('../api/client', () => ({
  api: { correlationTemperature: vi.fn(), correlationConcentration: vi.fn(), correlationEmissionsTemperature: vi.fn() },
}));
// Plotly's DOM lifecycle is design-system's own suite's concern; the series each widget hands SyChart is what is under test here.
vi.mock('design-system', async (orig) => ({
  ...(await orig<typeof import('design-system')>()),
  SyChart: (p: { ariaLabel?: string; series: Array<{ name: string; kind?: string; x: unknown[]; y: unknown[] }> }) => (
    <div data-testid="sychart" aria-label={p.ariaLabel} data-series={JSON.stringify(p.series.map((s) => [s.name, s.kind, s.x.length]))} />
  ),
}));

const FOSSIL = { ...HEADLINE_PAIR, variant: 'fossil', fit: { ...HEADLINE_PAIR.fit, slope: 0.797 } };

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((query: string) => ({ matches: false, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
  vi.mocked(api.correlationTemperature).mockImplementation(async (o) => (o?.view === 'mean5y' ? TEMPERATURE_MEAN5Y : TEMPERATURE));
  vi.mocked(api.correlationConcentration).mockResolvedValue(CONCENTRATION);
  vi.mocked(api.correlationEmissionsTemperature).mockImplementation(async (o) => (o?.variant === 'fossil' ? FOSSIL : HEADLINE_PAIR) as never);
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function widget(tool: string, props: unknown, over: Partial<WidgetSpec> = {}): WidgetSpec {
  return { intent: 'chart', chart_kind: null, title: 'Agent title', as_of: null, source_tool_call: `${tool}:{}`, props: props as Record<string, unknown>, ...over };
}
const mount = (w: WidgetSpec) => render(<MemoryRouter><WidgetRenderer widget={w} /></MemoryRouter>);

describe('the headline relationship', () => {
  it('is the module component, embedded: a level-3 heading and no page anchor id', async () => {
    mount(widget('get_emissions_temperature_relationship', HEADLINE_PAIR));
    expect(await screen.findByRole('heading', { level: 3, name: 'Global relationship' })).toBeInTheDocument();
    expect(document.getElementById('global-relationship')).toBeNull(); // the Correlation page's own anchor must not repeat inside an answer
  });

  it('uses the TOOL\'s own pair, so the stated slope is the one the tool returned', async () => {
    mount(widget('get_emissions_temperature_relationship', { ...HEADLINE_PAIR, fit: { ...HEADLINE_PAIR.fit, slope: 0.486 } }));
    await screen.findByRole('heading', { name: 'Global relationship' });
    expect(screen.getAllByText(/0\.486/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/0\.520/)).toBeNull();
  });

  it('keeps a valid heading hierarchy when embedded: the chart title is one level below the section title', async () => {
    mount(widget('get_emissions_temperature_relationship', HEADLINE_PAIR));
    await screen.findByRole('heading', { level: 3, name: 'Global relationship' });
    expect(screen.getByRole('heading', { level: 4, name: /Temperature anomaly vs cumulative CO₂/ })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 3, name: /Temperature anomaly vs cumulative CO₂/ })).toBeNull();
  });

  it('gives two headline answers in one thread unique ids (no duplicate-id markup)', async () => {
    render(
      <MemoryRouter>
        <WidgetRenderer widget={widget('get_emissions_temperature_relationship', HEADLINE_PAIR)} />
        <WidgetRenderer widget={widget('get_emissions_temperature_relationship', HEADLINE_PAIR)} />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getAllByRole('heading', { level: 3, name: 'Global relationship' })).toHaveLength(2));
    const ids = Array.from(document.querySelectorAll('[id]')).map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
    const [a, b] = screen.getAllByRole('heading', { level: 3, name: 'Global relationship' });
    expect(a.id).not.toBe(b.id);
    expect(a.closest('section')!.getAttribute('aria-labelledby')).toBe(a.id);
  });

  it('falls back to the pairs themselves when the module\'s extra data cannot load', async () => {
    vi.mocked(api.correlationConcentration).mockRejectedValue(new Error('down'));
    mount(widget('get_emissions_temperature_relationship', HEADLINE_PAIR));
    expect(await screen.findByTestId('sychart')).toBeInTheDocument();
    expect(screen.getByText(/Fitted slope 0\.520/)).toBeInTheDocument();
  });
});

describe('every other window is a plain pairs chart, never the headline', () => {
  it('the fossil-only variant', () => {
    mount(widget('get_emissions_temperature_relationship', FOSSIL, { title: 'Emissions vs. temperature (fossil-only variant, 1850–2024)' }));
    expect(screen.getByText('Emissions vs. temperature (fossil-only variant, 1850–2024)')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Global relationship' })).toBeNull();
    expect(JSON.parse(screen.getByTestId('sychart').dataset.series!)[0][1]).toBe('marker');
  });

  it('a 1990 window with no fit says so', () => {
    mount(widget('get_emissions_temperature_relationship', { ...HEADLINE_PAIR, baseline: '1990', fit: null }));
    expect(screen.getByText(/No fit is published for this window/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Global relationship' })).toBeNull();
  });

  it('the all-gas relationship is the module\'s all-gas component, embedded, and not titled as the headline', () => {
    mount(widget('get_emissions_temperature_relationship', ALL_GAS_PAIR));
    expect(screen.getByRole('heading', { level: 3, name: /Recent all-gas relationship/ })).toBeInTheDocument();
    expect(document.getElementById('recent-all-gas')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'Global relationship' })).toBeNull();
  });
});

describe('the greenhouse-gas mix', () => {
  it('a range is the module\'s composition component, embedded', () => {
    mount(widget('get_ghg_composition', COMPOSITION));
    expect(screen.getByRole('heading', { name: /Gas composition/ })).toBeInTheDocument();
    expect(document.getElementById('gas-composition')).toBeNull();
  });

  it('a single year is a small table of gases', () => {
    const one = { ...COMPOSITION, years: [COMPOSITION.years[COMPOSITION.years.length - 1]] };
    mount(widget('get_ghg_composition', one, { intent: 'grid', title: 'Greenhouse-gas mix, 2024' }));
    expect(screen.getByText('Greenhouse-gas mix, 2024')).toBeInTheDocument();
    // AG Grid renders no header or cell text in jsdom (same as every DataTable widget here): the card wiring is checked, the rows below.
  });

  it('builds the single-year rows with a dash, not zero, for a gas with no value', () => {
    const rows = singleYearRows({ years: [{ year: 2024, gases_included: [], values: [{ gas: 'co2', name: 'CO₂', mtco2e: 37500.4, share_pct: 74.96 }, { gas: 'fgas', name: 'Fluorinated gases', mtco2e: null, share_pct: null }] }] } as never);
    expect(rows).toEqual([{ gas: 'CO₂', mtco2e: '37,500', share: '75.0%' }, { gas: 'Fluorinated gases', mtco2e: '—', share: '—' }]);
    expect(singleYearRows({ years: [] } as never)).toEqual([]);
  });
});

describe('scenario temperatures', () => {
  it('is the module\'s scenario section, embedded (level-3 heading, no #scenarios id), fed the tool result', async () => {
    mount(widget('get_scenario_temperature', SCENARIO_TEMPERATURE));
    expect(await screen.findByRole('heading', { level: 3, name: /Implied temperature by scenario/ })).toBeInTheDocument();
    expect(document.getElementById('scenarios')).toBeNull();
  });

  it('keeps a valid heading hierarchy when embedded: both chart titles sit below the section title', async () => {
    mount(widget('get_scenario_temperature', SCENARIO_TEMPERATURE));
    await screen.findByRole('heading', { level: 3, name: /Implied temperature by scenario/ });
    expect(screen.getByRole('heading', { level: 4, name: /Annual emissions/ })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 4, name: /Implied temperature$/ })).toBeInTheDocument();
  });

  it('keeps the module\'s own reading note when the lead is composed, and drops it when the lead already carries it', async () => {
    const note = SCENARIO_TEMPERATURE.reading_note as string;
    const first = mount(widget('get_scenario_temperature', SCENARIO_TEMPERATURE));
    await screen.findByRole('heading', { level: 3, name: /Implied temperature by scenario/ });
    expect(screen.getByText(note)).toBeInTheDocument(); // composed lead: the section's panel is the only place the note appears
    first.unmount();

    mount(widget('get_scenario_temperature', SCENARIO_TEMPERATURE, { summary: { lead_includes_reading_note: true } }));
    await screen.findByRole('heading', { level: 3, name: /Implied temperature by scenario/ });
    expect(screen.queryByText(note)).toBeNull(); // the lead carries it: not printed a second time
    expect(screen.getByText(/Slope 0\.486|Implied temperature outcomes/)).toBeInTheDocument(); // the rest of the section is intact
  });

  it('says so, rather than drawing nothing, when the result cannot be drawn', async () => {
    mount(widget('get_scenario_temperature', { scenarios: {}, base: {}, assumptions: {} }));
    expect(await screen.findByText(/could not be drawn/)).toBeInTheDocument();
  });
});

describe('country shares', () => {
  it('a series is one line per country', () => {
    const r = shareResponse([['CHN', 'China', [[1990, 10, null], [2024, 15, null]]], ['USA', 'United States', [[1990, 25, null], [2024, 24, null]]]]);
    mount(widget('get_country_cumulative_share', r));
    expect(JSON.parse(screen.getByTestId('sychart').dataset.series!)).toEqual([['China', 'line', 2], ['United States', 'line', 2]]);
  });

  it('a ranking outside the data\'s coverage (200 with no rows) says so instead of drawing an empty chart', () => {
    const r = { ...shareResponse([]), mode: 'ranking', year: 1500, coverage: [1750, 2024], rows: [], notes: ['no data for 1500: coverage is 1750-2024'] };
    mount(widget('get_country_cumulative_share', r));
    expect(screen.queryByTestId('sychart')).toBeNull();
    expect(screen.getByText(/No country shares are available for 1500\. Coverage is 1750–2024\./)).toBeInTheDocument();
    expect(screen.getByText(/no data for 1500: coverage is 1750-2024/)).toBeInTheDocument();
  });

  it('a series for countries with no points is unavailable too, not an empty chart', () => {
    mount(widget('get_country_cumulative_share', shareResponse([])));
    expect(screen.queryByTestId('sychart')).toBeNull();
    expect(screen.getByText(/No country shares are available/)).toBeInTheDocument();
  });

  it('a ranking is one bar series', () => {
    const r = { ...shareResponse([]), mode: 'ranking', rows: [{ rank: 1, country: 'USA', name: 'United States', cumulative_mt: 1, share_pct: 24, annual_mt: null, annual_share_pct: null }] };
    mount(widget('get_country_cumulative_share', r));
    expect(JSON.parse(screen.getByTestId('sychart').dataset.series!)).toEqual([['Cumulative share', 'bar', 1]]);
  });
});

describe('concentration and temperature', () => {
  it('a "latest reading" is a KPI card with the year', () => {
    mount(widget('get_temperature_anomaly', TEMPERATURE, { intent: 'card', summary: { last_value: 1.451, last_year: 2025 }, title: 'Global temperature anomaly' }));
    expect(screen.getByText(/Temperature anomaly · 2025/)).toBeInTheDocument();
    expect(screen.getByText('1.45 °C')).toBeInTheDocument();
  });

  it('a range is a line chart', () => {
    mount(widget('get_co2_concentration', CONCENTRATION, { source_tool_call: 'get_co2_concentration:{}' }));
    expect(JSON.parse(screen.getByTestId('sychart').dataset.series!)[0][1]).toBe('line');
  });
});

describe('sources and methodology', () => {
  it('is a table of sources with the stale outputs called out', () => {
    mount(widget('get_correlation_metadata', META, { intent: 'grid', summary: { sources: [{ id: 'temperature_anomaly_annual', coverage: [1850, 2025], retrieved_at: '2026-10-06T00:00:00Z', license: 'cite' }], stale_outputs: ['correlation_headline.json'] }, title: 'Climate data sources and methodology' }));
    expect(screen.getByText('Climate data sources and methodology')).toBeInTheDocument();
    expect(screen.getByText(/missing or out of date: correlation_headline\.json/)).toBeInTheDocument();
  });

  it('builds the source rows: coverage as a range, the date only, a dash where none was recorded', () => {
    expect(sourceRows([{ id: 'a', coverage: [1850, 2025], retrieved_at: '2026-10-06T01:02:03Z', license: 'cite' }, { id: 'b' }])).toEqual([
      { source: 'a', coverage: '1850–2025', retrieved: '2026-10-06', licence: 'cite' },
      { source: 'b', coverage: '—', retrieved: '—', licence: '—' },
    ]);
  });
});

describe('the source line', () => {
  it('shows under the widget when the agent sent one, and not otherwise', () => {
    const { unmount } = mount(widget('get_ghg_composition', COMPOSITION, { source_line: 'Source: PRIMAP-hist national totals, CO₂e' }));
    expect(screen.getByText('Source: PRIMAP-hist national totals, CO₂e')).toBeInTheDocument();
    unmount();
    mount(widget('get_ghg_composition', COMPOSITION));
    expect(screen.queryByText(/^Source:/)).toBeNull();
  });
});
