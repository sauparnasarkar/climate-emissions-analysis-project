import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ThemeContext, THEME_STORAGE_KEY, type AppTheme } from './lib/theme';
import { DashboardLayout } from './layouts/DashboardLayout';
import { LandingLayout } from './layouts/LandingLayout';
import LandingPage from './pages/LandingPage';
import OverviewPage from './pages/OverviewPage';
import HistoricalTrendsPage from './pages/HistoricalTrendsPage';
import CountryProfilePage from './pages/CountryProfilePage';
import ForecastsPage from './pages/ForecastsPage';
import ScenarioComparisonPage from './pages/ScenarioComparisonPage';
import DataExplorerPage from './pages/DataExplorerPage';
import AboutPage from './pages/AboutPage';
import AdminPage from './pages/AdminPage';
import { AgentPage } from './pages/AgentPage';
import { AskThreadProvider } from './agent/AskThreadProvider';
import ClimateCorrelationPage from './pages/ClimateCorrelationPage';

function App() {
  // Read from localStorage in the initializer (not a useEffect) so a returning Dark user
  // never sees a flash of the other theme on first paint. Defaults to Dark -- "what a first-time
  // visitor lands on" -- for anyone with nothing stored yet, no prefers-color-scheme
  // detection (an explicit toggle exists; a media-query default would just contradict it).
  // Guarded: localStorage access can throw (Safari private browsing, an extension/policy
  // blocking storage), which would otherwise crash the app before it ever renders.
  const [theme, setTheme] = useState<AppTheme>(() => {
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY);
      return stored === 'analytics' || stored === 'analytics-bright-tidewater' ? stored : 'analytics';
    } catch {
      return 'analytics';
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Storage blocked -- the toggle still works for this session, it just won't persist
      // across reloads.
    }
  }, [theme]);

  return (
    <ThemeContext.Provider value={theme}>
      {/* Above every layout, so the Ask page's thread outlives navigating to any other page (including Home) and back. */}
      <AskThreadProvider>
      <Routes>
        {/* The landing page (Release 20, SPEC.md §5.25) has its own layout -- top nav, no sidebar. */}
        <Route element={<LandingLayout theme={theme} setTheme={setTheme} />}>
          <Route path="/" element={<LandingPage />} />
        </Route>
        {/* Everything else shares the dashboard shell. The Overview moved from '/' to '/overview'. */}
        <Route element={<DashboardLayout theme={theme} setTheme={setTheme} />}>
          <Route path="/overview" element={<OverviewPage />} />
          {/* Deliberately not '/agent' -- that path prefix is already claimed by the SSE proxy
              entry to services/agent's own backend (vite.config.ts's agentProxyEntry, matching
              the production Cloudflare route labs.syena.io/ghg-emissions-analysis/agent).
              Vite's dev proxy matches by path prefix, so a page route literally named '/agent'
              would itself get proxied to the backend instead of rendering the SPA -- confirmed
              live (ECONNREFUSED against the not-yet-running agent process the moment this page
              route was visited in dev). */}
          <Route path="/ask" element={<AgentPage />} />
          <Route path="/historical" element={<HistoricalTrendsPage />} />
          <Route path="/country-profile" element={<CountryProfilePage />} />
          <Route path="/forecasts" element={<ForecastsPage />} />
          <Route path="/scenarios" element={<ScenarioComparisonPage />} />
          <Route path="/data-explorer" element={<DataExplorerPage />} />
          <Route path="/climate-correlation" element={<ClimateCorrelationPage />} />
          <Route path="/about" element={<AboutPage />} />
          {/* Unlisted -- absent from NAV_ITEMS and SidebarNav.persistentAction, deliberately
              reachable by URL only (root ARCHITECTURE.md §8's admin capability, gated at the
              Cloudflare edge, not here). Same "route with no nav-surface presence" precedent
              '/ask' already sets, just with no persistentAction wiring at all. */}
          <Route path="/admin" element={<AdminPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </AskThreadProvider>
    </ThemeContext.Provider>
  );
}

export default App;
