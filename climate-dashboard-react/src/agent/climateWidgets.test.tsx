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
  SyChart: (p: { ariaLabel?: string; yTitle?: string; series: Array<{ name: string; kind?: string; x: unknown[]; y: unknown[] }> }) => (
    <div data-testid="sychart" aria-label={p.ariaLabel} data-ytitle={p.yTitle} data-series={JSON.stringify(p.series.map((s) => [s.name, s.kind, s.x.length]))} />
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

  describe('the cumulative views (Release 24.6)', () => {
    const point = (year: number, cumulative_mt: number, share_pct: number, annual_share_pct: number | null) => ({ year, cumulative_mt, share_pct, annual_mt: null, annual_share_pct });
    const remainder = (year: number, world: number) => ({ year, world_cumulative_mt: world, world_annual_mt: 1, cumulative_mt: 0, share_pct: 0, annual_mt: null, annual_share_pct: null, international_transport_cumulative_mt: null, international_transport_annual_mt: null });
    const owid = (names: Array<[string, string]>, over: Record<string, unknown> = {}) => ({
      ...shareResponse([]), source: 'owid_co2', mode: 'series',
      series: names.map(([code, name], i) => ({ country: code, name, points: [point(1990, 100 + i, 5, 6), point(2024, 285_000 + i, 15.4, 31.8)] })),
      remainder_series: [remainder(1990, 5000), remainder(2024, 1_849_000)],
      ...over,
    });
    const SUMMARY = { mode: 'series', countries: [{ name: 'China', last_year: 2024, last_share_pct: 15.4, first_year: 1990, first_share_pct: 5, last_cumulative_gt: 285.1, rank: 2, rank_of: 215 }] };
    const series = () => JSON.parse(screen.getByTestId('sychart').dataset.series!);

    it('cumulative_area is a stacked area in Gt with Rest of world on top, and a single country gets its three figures', () => {
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'cumulative_area', title: 'Cumulative CO₂ since records began, shown from 1990 – China', summary: SUMMARY }));
      expect(series()).toEqual([['China', 'area', 2], ['Rest of world', 'area', 2]]);
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('Stacked area chart of cumulative CO₂ in gigatonnes for China and Rest of world, 1990 to 2024'));
      expect(screen.getByText('285 GtCO₂')).toBeInTheDocument();
      expect(screen.getByText('15.4%')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
      expect(screen.getByText(/of 215 countries/)).toBeInTheDocument();
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', 'Cumulative CO₂ (GtCO₂)');
      expect(screen.getByText(/Rest of world = World total minus the countries shown/)).toBeInTheDocument();
    });

    it('several countries draw the stack without the single-country figures', () => {
      const two = { ...SUMMARY, countries: [SUMMARY.countries[0], { ...SUMMARY.countries[0], name: 'India' }] };
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China'], ['IND', 'India']]), { view: 'cumulative_area', summary: two }));
      expect(series().map((s: unknown[]) => s[0])).toEqual(['India', 'China', 'Rest of world']); // largest accumulated total at the bottom (India's fixture total is 1 Mt higher), Rest of world on top
      expect(screen.queryByText(/Rank by cumulative CO₂/)).toBeNull();
    });

    it("shows no start-share delta when the share was nil at the window's start (not a meaningful figure)", () => {
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'cumulative_area', summary: { ...SUMMARY, countries: [{ ...SUMMARY.countries[0], first_share_pct: 0.0, first_year: 1907 }] } }));
      expect(screen.getByText('15.4%')).toBeInTheDocument();
      expect(screen.queryByText(/in 1907/)).toBeNull();
      cleanup();
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'cumulative_area', summary: SUMMARY }));
      expect(screen.getByText('5.0% in 1990')).toBeInTheDocument(); // a real starting share is shown
    });

    it('a since-answer draws the area from zero with its own figures and period, never "since records began"', () => {
      const since = { year: 1990, period: '1990–2024', rank_of: 215, world_base_cumulative_mt: 5000, countries: [{ name: 'China', emitted_gt: 244.2, share_of_period_pct: 22.9, rank: 2, base_cumulative_mt: 100 }] };
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'cumulative_area', title: 'Emitted 1990–2024, GtCO₂ – China', summary: { ...SUMMARY, since } }));
      expect(screen.getByText('Emitted 1990–2024')).toBeInTheDocument();
      expect(screen.getByText('244 GtCO₂')).toBeInTheDocument();
      expect(screen.getByText("Share of the world's emissions 1990–2024")).toBeInTheDocument();
      cleanup();
      const sinceP = { ...since, countries: [{ name: 'China', emitted_gt: 200.0, share_of_period_pct: 25.0, rank: 1 }] };
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']], { source: 'primap_hist', gas_scope: 'co2', remainder_series: [] }), { view: 'share_vs_annual', summary: { ...SUMMARY, since: sinceP } }));
      expect(screen.getByText("Share of PRIMAP-hist's own total 1990–2024")).toBeInTheDocument();
      cleanup();
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'cumulative_area', title: 'Emitted 1990–2024, GtCO₂ – China', summary: { ...SUMMARY, since } }));
      expect(screen.getByText('22.9%')).toBeInTheDocument();
      expect(screen.getByText('#2')).toBeInTheDocument();
      expect(screen.getByText(/emissions in 1990–2024: each country's cumulative total in each year minus its total the year before 1990, so every area starts at zero/)).toBeInTheDocument();
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('CO₂ emitted 1990–2024 in gigatonnes'));
      expect(screen.queryByText(/since records began/)).toBeNull();
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', 'CO₂ emitted 1990–2024 (GtCO₂)'); // the axis names the period, not "Cumulative CO₂"
    });

    it('a PRIMAP-hist since-answer is lines of emissions in the period (no World total for a Rest of world), in its own gas and unit, never the lifetime share lines', () => {
      const since = { year: 1990, period: '1990–2024', rank_of: 207, world_base_cumulative_mt: 5000, countries: [{ name: 'China', emitted_gt: 300.0, share_of_period_pct: 24.0, rank: 1, base_cumulative_mt: 100 }] };
      const r = owid([['CHN', 'China']], { source: 'primap_hist', gas_scope: 'total_ghg', remainder_series: [] });
      mount(widget('get_country_cumulative_share', r, { view: 'emitted_lines', title: 'Emitted 1990–2024, GtCO₂e – China', summary: { ...SUMMARY, since } }));
      expect(series()).toEqual([['China', 'line', 2]]);
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', 'Greenhouse gases (CO₂e) emitted 1990–2024 (GtCO₂e)');
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('greenhouse gases (CO₂e) emitted 1990–2024 in gigatonnes for China'));
      expect(screen.getByText('Emitted 1990–2024')).toBeInTheDocument();
      expect(screen.getByText('300 GtCO₂e')).toBeInTheDocument();
      expect(screen.getByText("Share of PRIMAP-hist's own total 1990–2024")).toBeInTheDocument();
      expect(screen.getByText(/PRIMAP-hist total greenhouse gases \(CO₂e\) · emissions in 1990–2024: each country.s cumulative total in each year minus its total the year before 1990, so every line starts at zero/)).toBeInTheDocument();
      expect(screen.getByText(/no World total here to show a Rest of world against/)).toBeInTheDocument();
      expect(screen.queryByText(/Cumulative .* since records began/)).toBeNull();
    });

    it('reads the basis of a period share from the data: an older OWID output without a World remainder is of the country total, never claimed as the world\'s emissions', () => {
      const legacy = { year: 1990, period: '1990–2024', rank_of: 215, basis: "share of the source's own total emissions in the period", world_base_cumulative_mt: 5000, countries: [{ name: 'China', emitted_gt: 200.0, share_of_period_pct: 25.0, rank: 1, base_cumulative_mt: 100 }] };
      const r = owid([['CHN', 'China']], { remainder_series: [], denominator: { kind: 'country_sum' } }); // OWID, but the pipeline output predates the World total
      mount(widget('get_country_cumulative_share', r, { view: 'emitted_lines', title: 'Emitted 1990–2024, GtCO₂ – China', summary: { ...SUMMARY, since: legacy } }));
      expect(screen.getByText('Share of the country total 1990–2024')).toBeInTheDocument();
      expect(screen.queryByText("Share of the world's emissions 1990–2024")).toBeNull();
      expect(screen.getByText(/Fossil and cement CO₂ · OWID · emissions in 1990–2024/)).toBeInTheDocument(); // still OWID, not PRIMAP-hist
      expect(screen.getByText(/no World total here to show a Rest of world against/)).toBeInTheDocument(); // true for this output; the old text claimed it of "this source"
      cleanup();
      const world = { ...legacy, basis: "share of the World's emissions in the period (international aviation and shipping included)" };
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']], { denominator: { kind: 'world' } }), { view: 'cumulative_area', summary: { ...SUMMARY, since: world } }));
      expect(screen.getByText("Share of the world's emissions 1990–2024")).toBeInTheDocument();
    });

    it('a ranking since a year is bars of Gt emitted in the period, not the share bars', () => {
      const r = { ...shareResponse([]), mode: 'ranking', year: 2024, since_year: 1970, rows: [], since_rows: [
        { rank: 1, country: 'USA', name: 'United States', emitted_mt: 284_700, emitted_gt: 284.7, emitted_text: '284.7 GtCO₂', share_of_period_pct: 30.0 },
        { rank: 2, country: 'CHN', name: 'China', emitted_mt: 275_000, emitted_gt: 275.0, emitted_text: '275.0 GtCO₂', share_of_period_pct: 29.0 },
      ] };
      mount(widget('get_country_cumulative_share', r, { title: 'Top 2 emitters, 1970–2024, GtCO₂', summary: { mode: 'ranking', since: { year: 1970, period: '1970–2024' } } }));
      expect(JSON.parse(screen.getByTestId('sychart').dataset.series!)).toEqual([['Emitted 1970–2024', 'bar', 2]]);
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('CO₂ emitted 1970–2024 in gigatonnes for the 2 largest emitters'));
      expect(screen.getByText(/cumulative total at the end year minus its total the year before 1970/)).toBeInTheDocument();
      expect(screen.queryByText(/No country shares are available/)).toBeNull();
    });

    it('labels a PRIMAP-hist total-greenhouse-gas ranking in CO₂e with its own source, never as OWID CO₂', () => {
      const r = { ...shareResponse([]), source: 'primap_hist', gas_scope: 'total_ghg', mode: 'ranking', year: 2024, since_year: 1970, rows: [], since_rows: [
        { rank: 1, country: 'USA', name: 'United States', emitted_mt: 400_000, emitted_gt: 400.0, emitted_text: '400.0 GtCO₂e', share_of_period_pct: 30.0 },
      ] };
      mount(widget('get_country_cumulative_share', r, { title: 'Top 1 emitters, 1970–2024, GtCO₂e', summary: { mode: 'ranking', since: { year: 1970, period: '1970–2024' } } }));
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', 'Greenhouse gases (CO₂e) emitted 1970–2024 (GtCO₂e)');
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('greenhouse gases (CO₂e) emitted 1970–2024'));
      expect(screen.getByText(/PRIMAP-hist total greenhouse gases \(CO₂e\) · emissions in 1970–2024/)).toBeInTheDocument();
      expect(screen.getByText(/Shares of the period are of PRIMAP-hist's own total in it\./)).toBeInTheDocument(); // not 'the World's emissions': PRIMAP-hist has no world aggregate
      expect(screen.queryByText(/Fossil and cement CO₂ · OWID/)).toBeNull();
    });

    it("a single country's figures use the result's own unit and source (GtCO₂e for PRIMAP total greenhouse gases)", () => {
      const ghg = owid([['CHN', 'China']], { source: 'primap_hist', gas_scope: 'total_ghg', remainder_series: [] });
      mount(widget('get_country_cumulative_share', ghg, { view: 'share_vs_annual', summary: SUMMARY }));
      expect(screen.getByText('285 GtCO₂e')).toBeInTheDocument();
      expect(screen.getByText('Cumulative greenhouse gases (CO₂e) since records began · 2024')).toBeInTheDocument();
      expect(screen.getByText('Rank by cumulative greenhouse gases (CO₂e) · 2024')).toBeInTheDocument(); // not 'Rank by cumulative CO₂'
      expect(screen.getByText('PRIMAP-hist')).toBeInTheDocument();
      expect(screen.queryByText('Fossil and cement')).toBeNull();
      expect(screen.getByText("Share of PRIMAP-hist's own total")).toBeInTheDocument(); // not 'Share of world total': it has no world aggregate
      expect(screen.queryByText('Share of world total')).toBeNull();
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', "% of PRIMAP-hist's own total"); // not '% of world'
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining("each year's greenhouse gases (CO₂e) emissions, as a percent of PRIMAP-hist's own total"));
      expect(screen.getByText(/Solid line: share of all greenhouse gases \(CO₂e\) emitted so far/)).toBeInTheDocument();
    });

    it('share_vs_annual is the solid-against-dotted pair for one country', () => {
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'share_vs_annual', title: 'Share of cumulative CO₂ against share of each year\'s emissions – China', summary: SUMMARY }));
      expect(series()).toEqual([['Share of cumulative total', 'line', 2], ["Share of that year's emissions", 'line', 2]]);
      expect(screen.getByText(/When the dotted line is above the solid one, the share of the total is still rising/)).toBeInTheDocument();
      expect(screen.getByTestId('sychart')).toHaveAttribute('data-ytitle', '% of world total');
      expect(screen.getByTestId('sychart')).toHaveAttribute('aria-label', expect.stringContaining('as a percent of world total'));
      expect(screen.getByText('285 GtCO₂')).toBeInTheDocument();
    });

    it('a view that cannot be drawn honestly falls back to the share lines (PRIMAP-hist has no World total; no annual share)', () => {
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']], { source: 'primap_hist', remainder_series: [] }), { view: 'cumulative_area', summary: SUMMARY }));
      expect(series()).toEqual([['China', 'line', 2]]);
      cleanup();
      const noAnnual = owid([['CHN', 'China']]);
      noAnnual.series[0].points = noAnnual.series[0].points.map((p) => ({ ...p, annual_share_pct: null }));
      mount(widget('get_country_cumulative_share', noAnnual, { view: 'share_vs_annual', summary: SUMMARY }));
      expect(series()).toEqual([['China', 'line', 2]]);
    });

    it('share_lines, an absent view (an older agent) and a ranking are drawn as before', () => {
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']]), { view: 'share_lines' }));
      expect(series()).toEqual([['China', 'line', 2]]);
      cleanup();
      mount(widget('get_country_cumulative_share', owid([['CHN', 'China']])));
      expect(series()).toEqual([['China', 'line', 2]]);
      expect(screen.queryByText(/GtCO₂/)).toBeNull();
    });
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
