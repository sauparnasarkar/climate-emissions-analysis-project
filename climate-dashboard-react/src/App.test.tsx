import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import App from './App';

// The landing page's data never resolves here: routing tests only need its static shell (headline, CTA).
vi.mock('./api/client', () => ({ api: { overview: () => new Promise(() => {}), worldMapSeries: () => new Promise(() => {}) } }));

// Page bodies are covered by their own suites -- this file only tests routing and the two layouts.
vi.mock('./pages/OverviewPage', () => ({ default: () => <div>Overview page stub</div> }));
vi.mock('./pages/HistoricalTrendsPage', () => ({ default: () => <div>Historical page stub</div> }));
vi.mock('./pages/CountryProfilePage', () => ({ default: () => <div>Country profile stub</div> }));
vi.mock('./pages/ForecastsPage', () => ({ default: () => <div>Forecasts stub</div> }));
vi.mock('./pages/ScenarioComparisonPage', () => ({ default: () => <div>Scenarios stub</div> }));
vi.mock('./pages/DataExplorerPage', () => ({ default: () => <div>Data explorer stub</div> }));
vi.mock('./pages/AboutPage', () => ({ default: () => <div>About page stub</div> }));
vi.mock('./pages/AdminPage', () => ({ default: () => <div>Admin page stub</div> }));
vi.mock('./pages/AgentPage', () => ({ AgentPage: () => <div>Agent page stub</div> }));

// jsdom has no matchMedia; design-system's useIsMobile/useReducedMotion call it during render.
// Desktop viewport by default (only `(max-width: 768px)` flips with `mobile`); never reduced-motion.
let mobile = false;
beforeAll(() => {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: mobile && query === '(max-width: 768px)', media: query, addEventListener: () => {}, removeEventListener: () => {},
    addListener: () => {}, removeListener: () => {}, dispatchEvent: () => false, onchange: null,
  }));
});
afterEach(() => { mobile = false; });

const renderAt = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe('App routing (Release 20)', () => {
  it('renders the landing page at "/" with the top-nav layout, not the dashboard sidebar', () => {
    renderAt('/');
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂ comes from/i })).toBeInTheDocument();
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    // Every dashboard page is reachable from the landing nav, with the app's exact labels.
    for (const label of ['Overview', 'Historical Trends', 'Country Profile', 'Data Explorer', 'Forecasts', 'Scenario Comparison', 'About']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(within(nav).getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/overview');
    expect(screen.queryByText('Overview page stub')).not.toBeInTheDocument();
    expect(document.title).toBe('GHG Emissions Analytics');
  });

  it('moved the Overview from "/" to "/overview", inside the dashboard shell', () => {
    renderAt('/overview');
    expect(screen.getByText('Overview page stub')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { level: 1, name: /where the world’s co₂/i })).not.toBeInTheDocument();
    expect(document.title).toBe('Overview — GHG Emissions Trend Analysis and Forecasting');
  });

  it('has a Home sidebar item that returns to "/" and an Overview item that opens "/overview"', () => {
    renderAt('/historical');
    // SidebarNav items are role="menuitem" anchors wired through onItemClick.
    expect(screen.getByRole('menuitem', { name: 'Overview' })).toHaveAttribute('href', '/overview');
    expect(screen.getByRole('menuitem', { name: 'Home' })).toHaveAttribute('href', '/');
    fireEvent.click(screen.getByRole('menuitem', { name: 'Overview' }));
    expect(screen.getByText('Overview page stub')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('menuitem', { name: 'Home' }));
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂/i })).toBeInTheDocument();
  });

  it.each([
    ['/historical', 'Historical page stub'],
    ['/country-profile', 'Country profile stub'],
    ['/forecasts', 'Forecasts stub'],
    ['/scenarios', 'Scenarios stub'],
    ['/data-explorer', 'Data explorer stub'],
    ['/about', 'About page stub'],
    ['/ask', 'Agent page stub'],
    ['/admin', 'Admin page stub'],
  ])('still serves %s under the dashboard shell', (path, text) => {
    renderAt(path);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it('redirects an unknown path to the landing page', () => {
    renderAt('/no-such-page');
    expect(screen.getByRole('heading', { level: 1, name: /where the world’s co₂/i })).toBeInTheDocument();
  });

  it('renders the landing CTA as one link, not a button nested inside a link', () => {
    renderAt('/');
    const cta = screen.getByRole('link', { name: 'Explore the data' });
    expect(cta).toHaveAttribute('href', '/overview');
    expect(within(cta).queryByRole('button')).not.toBeInTheDocument();
    expect(cta.closest('a')?.querySelector('button')).toBeNull();
  });
});

describe('Landing layout on a phone (< 768px)', () => {
  it('hides the inline nav behind a Menu button that discloses nav, theme toggle and Ask the Agent', () => {
    mobile = true;
    renderAt('/');
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
    const menu = screen.getByRole('button', { name: 'Menu' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(menu);
    expect(menu).toHaveAttribute('aria-expanded', 'true');
    const nav = screen.getByRole('navigation', { name: 'Primary' });
    for (const label of ['Overview', 'Historical Trends', 'Country Profile', 'Data Explorer', 'Forecasts', 'Scenario Comparison', 'About']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument();
    }
    expect(within(nav).getByRole('link', { name: 'Ask the Agent' })).toHaveAttribute('href', '/ask');
    expect(within(nav).getByRole('radio', { name: 'Dark' })).toBeInTheDocument();
  });

  it('closes on Escape and on following a link', () => {
    mobile = true;
    renderAt('/');
    const menu = screen.getByRole('button', { name: 'Menu' });

    fireEvent.click(menu);
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
    expect(menu).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(menu);
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Primary' })).getByRole('link', { name: 'About' }));
    // Navigated to a dashboard page, which is a different layout entirely (its phone header has its own
    // "Menu" button, but the landing dropdown is gone).
    expect(screen.getByText('About page stub')).toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Primary' })).not.toBeInTheDocument();
  });
});

describe('Dashboard header actions (same place as the landing header)', () => {
  it('desktop: the theme toggle and Ask the Agent sit together in the header, and the sidebar no longer duplicates Ask', () => {
    renderAt('/about');
    const header = screen.getByRole('banner');
    expect(within(header).getByRole('radio', { name: 'Dark' })).toBeInTheDocument();
    expect(within(header).getByRole('link', { name: 'Ask the Agent' })).toHaveAttribute('href', '/ask');
    // The persistent-action button is phone-only now.
    expect(screen.queryByRole('button', { name: 'Ask the Agent' })).not.toBeInTheDocument();
  });

  it('marks Ask the Agent as the current page on /ask', () => {
    renderAt('/ask');
    expect(within(screen.getByRole('banner')).getByRole('link', { name: 'Ask the Agent' })).toHaveAttribute('aria-current', 'page');
  });

  it('phone: the header has the same bordered Menu button as the landing page; Ask and the toggle live in the drawer it opens', () => {
    mobile = true;
    renderAt('/about');
    const header = screen.getByRole('banner');
    const menu = within(header).getByRole('button', { name: 'Menu' });
    expect(menu).toHaveAttribute('aria-expanded', 'false');
    expect(within(header).queryByRole('link', { name: 'Ask the Agent' })).not.toBeInTheDocument();
    expect(within(header).queryByRole('radio')).not.toBeInTheDocument();
    // SidebarNav's own floating menu button and floating Ask action are switched off.
    expect(screen.queryByRole('button', { name: 'Open menu' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Ask the Agent' })).not.toBeInTheDocument();

    fireEvent.click(menu);
    const drawer = screen.getByRole('dialog');
    expect(within(drawer).getByRole('link', { name: 'Ask the Agent' })).toHaveAttribute('href', '/ask');
    expect(within(drawer).getAllByRole('radio', { name: 'Dark' })).toHaveLength(1); // exactly one toggle live, in the drawer
    expect(within(drawer).getByRole('menuitem', { name: 'Overview' })).toBeInTheDocument();
  });

  it('phone: choosing a page in the drawer closes it and navigates', () => {
    mobile = true;
    renderAt('/about');
    fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('menuitem', { name: 'Overview' }));
    expect(screen.getByText('Overview page stub')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('phone: the Ask link inside the drawer also closes it on navigation', () => {
    mobile = true;
    renderAt('/about');
    fireEvent.click(screen.getByRole('button', { name: 'Menu' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('link', { name: 'Ask the Agent' }));
    expect(screen.getByText('Agent page stub')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
