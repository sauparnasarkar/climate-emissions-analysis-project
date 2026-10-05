import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import { ApiError } from '../../api/types';
import { buildComposition } from '../../lib/gasComposition';
import { COMPOSITION, COUNTRY_SNAPSHOT, sp } from '../../test/climateFixtures';
import { shareResponse } from '../../test/shareFixtures';
import { CountryView } from './CountryView';
import { GasComposition } from './GasComposition';

vi.mock('../../api/client', () => ({ api: { correlationCountryShare: vi.fn() } }));
vi.mock('design-system', async (orig) => ({
  ...(await orig<typeof import('design-system')>()),
  SyChart: (p: { ariaLabel?: string; stackedAreaMode?: string; series: Array<{ name: string; kind?: string; color?: string; y: Array<number | null> }> }) => (
    <div data-testid="sychart" aria-label={p.ariaLabel} data-stacked={p.stackedAreaMode} data-series={JSON.stringify(p.series.map((s) => [s.name, s.kind, s.color]))} />
  ),
}));

beforeEach(() => {
  vi.stubGlobal('matchMedia', vi.fn().mockImplementation((q: string) => ({ matches: false, media: q, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
});
afterEach(() => { cleanup(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

const dense = () => {
  const c = JSON.parse(JSON.stringify(COMPOSITION));
  const base = c.years[2];
  c.years = [2021, 2022, 2023, 2024].map((year, i) => ({ ...base, year, values: base.values.map((v: { mtco2e: number }) => ({ ...v, mtco2e: v.mtco2e * (1 + i / 10) })) }));
  return buildComposition(c)!;
};

describe('GasComposition', () => {
  it('draws a 100%-stacked area with one coloured series per gas, and the latest year\'s split with its table', () => {
    render(<GasComposition composition={buildComposition(COMPOSITION)!} />);
    expect(screen.getByRole('heading', { level: 3, name: 'Gas composition, 1970 onward' })).toBeInTheDocument();
    const chart = screen.getByTestId('sychart');
    expect(chart).toHaveAttribute('data-stacked', 'percent');
    expect(JSON.parse(chart.getAttribute('data-series')!).map((s: string[]) => [s[0], s[1]])).toEqual([['CO₂', 'area'], ['CH₄', 'area'], ['N₂O', 'area'], ['Fluorinated gases', 'area']]);
    expect(screen.getByText('Greenhouse gases by share, 2024')).toBeInTheDocument();
    const row = screen.getByRole('row', { name: /^CO₂/ });
    expect(within(row).getByText('75.1%')).toBeInTheDocument();
    expect(within(row).getByText('37,974')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /^Gas split: CO₂ 75\.1%/ })).toBeInTheDocument();
  });

  it('the baseline chip gives the source data range (requirements §2.5), not a source name', () => {
    render(<GasComposition composition={buildComposition(COMPOSITION)!} />);
    expect(screen.getByText('Baseline none · shares of each year · 1970–2024')).toBeInTheDocument();
  });

  it('discloses how far the four gases sit from PRIMAP-hist\'s own national total, for the year shown', () => {
    render(<GasComposition composition={buildComposition(COMPOSITION)!} />);
    expect(screen.getByText(/Together they sit 0\.05% above PRIMAP-hist's own national total for 2024 \(largest gap in any year 0\.21%, held to within 1%\)/)).toBeInTheDocument();
  });

  it('states the API\'s basis and the incomplete year it left out, with the caveats behind a disclosure and no licences', () => {
    render(<GasComposition composition={buildComposition(COMPOSITION)!} />);
    expect(screen.getByText(/AR5 100-year global-warming potentials/)).toBeInTheDocument();
    expect(screen.getByText(/Incomplete trailing year left out: 2025/)).toBeInTheDocument();
    expect(screen.getAllByText(/2025/)).toHaveLength(1); // stated once, not again in the disclosure
    const details = screen.getByText('What this covers, and what it leaves out').closest('details') as HTMLElement;
    expect(within(details).getByText(/excludes deforestation/)).toBeInTheDocument();
    expect(within(details).queryByText(/licence/i)).not.toBeInTheDocument();
  });

  it('the keyboard can cross a missing year: a step lands on the next available year in the direction of travel', () => {
    const c = JSON.parse(JSON.stringify(COMPOSITION));
    const base = c.years[2];
    c.years = [2020, 2021, 2023, 2024].map((year) => ({ ...base, year })); // 2022 has no full split
    render(<GasComposition composition={buildComposition(c)!} />);
    const slider = screen.getByRole('slider');
    fireEvent.keyDown(slider, { key: 'ArrowLeft' });
    expect(screen.getByText('Greenhouse gases by share, 2023')).toBeInTheDocument();
    fireEvent.keyDown(slider, { key: 'ArrowLeft' }); // 2022 is missing: it must go on to 2021, not stay on 2023
    expect(screen.getByText('Greenhouse gases by share, 2021')).toBeInTheDocument();
    fireEvent.keyDown(slider, { key: 'ArrowRight' });
    expect(screen.getByText('Greenhouse gases by share, 2023')).toBeInTheDocument();
  });

  it('the gas split bar announces only the four gases, with no phantom remainder category', () => {
    render(<GasComposition composition={buildComposition(COMPOSITION)!} />);
    const bar = screen.getByRole('img', { name: /^Gas split:/ });
    expect(bar.getAttribute('aria-label')).toMatch(/CO₂ 75\.1%, CH₄ 16\.7%, N₂O 5\.4%, Fluorinated gases 2\.8%$/);
    expect(bar.getAttribute('aria-label')).not.toMatch(/Rest of world/);
    expect(bar.children).toHaveLength(4);
  });

  it('moves the split with the year slider, onto the nearest year that has data', () => {
    render(<GasComposition composition={dense()} />);
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('aria-valuemax', '2024');
    fireEvent.keyDown(slider, { key: 'ArrowLeft' });
    expect(screen.getByText('Greenhouse gases by share, 2023')).toBeInTheDocument();
  });
});

describe('CountryView', () => {
  const TEMP = [2022, 2023, 2024].map((y, i) => ({ year: y, value: 1.4 + i * 0.1 }));
  const SERIES = shareResponse([['USA', 'United States', [[1850, 4, 1], [2024, 24.1, 1]]], ['CHN', 'China', [[1850, 1, 1], [2024, 15.8, 1]]]]);
  beforeEach(() => {
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : { ...SERIES, cumulative_from: 1750 }));
  });
  const mount = () => render(<CountryView temperature={TEMP} mean5y={[sp(2023, 1.35), sp(2024, 1.39)].map((p) => ({ year: p.year, value: p.value as number }))} />);

  it('says up front that no country is regressed against temperature and no warming is attributed to a country', async () => {
    mount();
    expect(await screen.findByText(/No country series is regressed against temperature, and no warming is attributed to a country/)).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Country view' })).toBeInTheDocument();
  });

  it('starts with the five largest cumulative emitters from the ranked snapshot and asks for their shares from 1850', async () => {
    mount();
    await screen.findByText('Share of cumulative CO₂, 2024');
    expect(api.correlationCountryShare).toHaveBeenCalledWith({ allCountries: true });
    expect(api.correlationCountryShare).toHaveBeenCalledWith({ countries: ['USA', 'CHN', 'RUS', 'DEU', 'GBR'], startYear: 1850 });
    expect(screen.getByRole('columnheader', { name: 'Country' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Share' })).toBeInTheDocument();
    expect(screen.getByRole('row', { name: /United States/ })).toHaveTextContent('24.1%');
    expect(screen.getByText('Baseline cumulative since 1750 · national sum, bunkers excluded · OWID')).toBeInTheDocument();
  });

  it('draws the global temperature record beside it: annual and 5-year mean, one global line, not a country', async () => {
    mount();
    await screen.findByText('Share of cumulative CO₂, 2024');
    const charts = screen.getAllByTestId('sychart');
    const temp = charts.find((c) => c.getAttribute('aria-label')?.startsWith('Line chart of the global temperature'))!;
    expect(temp).toHaveAttribute('aria-label', expect.stringContaining('5-year mean'));
    expect(JSON.parse(temp.getAttribute('data-series')!).map((s: string[]) => s[0])).toEqual(['Annual', '5-year mean']);
    expect(screen.getByText('Global temperature anomaly')).toBeInTheDocument();
  });

  it('refetches when a country is added, and hides the previous lines while it loads', async () => {
    mount();
    await screen.findByText('Share of cumulative CO₂, 2024');
    let answer!: (r: typeof SERIES) => void;
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : new Promise((r) => { answer = r; })));
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    await user.click(screen.getByLabelText('Countries (up to 10)'));
    await user.click(screen.getByRole('option', { name: 'Japan' }));
    expect(api.correlationCountryShare).toHaveBeenLastCalledWith({ countries: ['USA', 'CHN', 'RUS', 'DEU', 'GBR', 'JPN'], startYear: 1850 });
    expect(await screen.findByText('Loading…')).toBeInTheDocument();
    expect(screen.queryByText('Share of cumulative CO₂, 2024')).not.toBeInTheDocument();
    await act(async () => answer(SERIES));
    expect(await screen.findByText('Share of cumulative CO₂, 2024')).toBeInTheDocument();
  });

  it('names a country with no data and leaves it out; shows the API\'s message when the request fails', async () => {
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : { ...shareResponse([['USA', 'United States', [[1850, 4, 1], [2024, 24, 1]]], ['CHN', 'China', []]]), notes: ['no rows for CHN'] }));
    mount();
    expect(await screen.findByText(/No data for China; it is left out\. no rows for CHN/)).toBeInTheDocument();
    expect(screen.queryByRole('row', { name: /China/ })).not.toBeInTheDocument();
    cleanup();
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => { if (o?.allCountries) return COUNTRY_SNAPSHOT; throw new ApiError(404, 'unknown country code(s): XXX'); });
    mount();
    expect(await screen.findByText(/unknown country code\(s\): XXX/)).toBeInTheDocument();
  });

  it('explains an empty snapshot (a 200 with no rows and a coverage note) instead of an empty picker and a bare prompt', async () => {
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? { ...COUNTRY_SNAPSHOT, rows: [], coverage: [1850, 2023], year: 2024, notes: ['no data for 2024: coverage is 1850-2023'] } : SERIES));
    mount();
    expect(await screen.findByText(/No country shares are available for 2024\. Coverage is 1850–2023\. no data for 2024/)).toBeInTheDocument();
    expect(screen.queryByText('Choose countries to compare their shares.')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Countries (up to 10)')).not.toBeInTheDocument();
  });

  it('names every selected country and shows the API\'s note when none of them has data, with no empty chart', async () => {
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : { ...shareResponse([['USA', 'United States', []], ['CHN', 'China', []]]), notes: ['no rows in this range'] }));
    mount();
    expect(await screen.findByText(/No data for United States, China; they are left out\. no rows in this range/)).toBeInTheDocument();
    expect(screen.queryByText(/Share of cumulative CO₂, 2024/)).not.toBeInTheDocument();
    expect(screen.queryByText('No share data is available for these countries.')).not.toBeInTheDocument();
  });

  it('labels a share with its own year when a country\'s series ends before the latest year', async () => {
    vi.mocked(api.correlationCountryShare).mockImplementation(async (o) => (o?.allCountries ? COUNTRY_SNAPSHOT : shareResponse([['USA', 'United States', [[1850, 4, 1], [2024, 24.1, 1]]], ['CHN', 'China', [[1850, 1, 1], [2019, 12.5, 1]]]])));
    mount();
    await screen.findByText('Share of cumulative CO₂, 2024');
    expect(screen.getByRole('row', { name: /United States/ })).toHaveTextContent('24.1%');
    expect(screen.getByRole('row', { name: /United States/ }).textContent).not.toMatch(/\(2024\)/);
    expect(screen.getByRole('row', { name: /China/ })).toHaveTextContent('12.5% (2019)');
    expect(screen.getByLabelText(/Latest values: United States 24\.1% in 2024, China 12\.5% \(2019\)/)).toBeInTheDocument();
  });

  it('omits the temperature card without data rather than drawing an empty chart', async () => {
    render(<CountryView temperature={[]} mean5y={null} />);
    await screen.findByText('Share of cumulative CO₂, 2024');
    expect(screen.queryByText('Global temperature anomaly')).not.toBeInTheDocument();
  });
});
