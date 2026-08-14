import { useEffect, useRef } from 'react';
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Header, SidebarNav, Footer, BackToTop } from 'design-system';
import type { SidebarNavItem, SidebarNavGroup } from 'design-system/components/SidebarNav/SidebarNav';

import OverviewPage from './pages/OverviewPage';
import HistoricalTrendsPage from './pages/HistoricalTrendsPage';
import CountryProfilePage from './pages/CountryProfilePage';
import ForecastsPage from './pages/ForecastsPage';
import ScenarioComparisonPage from './pages/ScenarioComparisonPage';
import DataExplorerPage from './pages/DataExplorerPage';
import AboutPage from './pages/AboutPage';
import { AgentPage } from './pages/AgentPage';

// `group` is omitted for About, which is meta-content pinned to the sidebar's existing
// footerItems slot rather than clustered with either group.
const NAV_ITEMS: Array<Omit<SidebarNavItem, 'active'> & { path: string; group?: 'Exploration' | 'Projection' }> = [
  { id: 'overview', label: 'Overview', icon: 'home', path: '/', group: 'Exploration' },
  // services/agent's conversational agent (SPEC.md §1-§2) -- spans both historical and forecast
  // questions (§4's starter prompts), so it leads the Exploration group rather than sitting in
  // either group's middle.
  // Deliberately not '/agent' -- that path prefix is already claimed by the SSE proxy entry to
  // services/agent's own backend (vite.config.ts's agentProxyEntry, matching the production
  // Cloudflare route labs.syena.io/ghg-emissions-analysis/agent). Vite's dev proxy matches by
  // path prefix, so a page route literally named '/agent' would itself get proxied to the
  // backend instead of rendering the SPA -- confirmed live (ECONNREFUSED against the
  // not-yet-running agent process the moment this page route was visited in dev).
  { id: 'agent', label: 'Ask the Agent', icon: 'send', path: '/ask', group: 'Exploration' },
  { id: 'historical', label: 'Historical Trends', icon: 'document', path: '/historical', group: 'Exploration' },
  { id: 'country-profile', label: 'Country Profile', icon: 'user', path: '/country-profile', group: 'Exploration' },
  { id: 'data-explorer', label: 'Data Explorer', icon: 'search', path: '/data-explorer', group: 'Exploration' },
  { id: 'forecasts', label: 'Forecasts', icon: 'calendar', path: '/forecasts', group: 'Projection' },
  { id: 'scenarios', label: 'Scenario Comparison', icon: 'grid', path: '/scenarios', group: 'Projection' },
  { id: 'about', label: 'About', icon: 'info', path: '/about' },
];

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const mainRef = useRef<HTMLElement>(null);
  const isFirstRender = useRef(true);

  const toItem = ({ path, group, ...item }: (typeof NAV_ITEMS)[number]): SidebarNavItem => ({
    ...item,
    href: path,
    active: location.pathname === path,
  });
  const groups: SidebarNavGroup[] = (['Exploration', 'Projection'] as const).map((label) => ({
    label,
    items: NAV_ITEMS.filter((item) => item.group === label).map(toItem),
  }));
  const footerItems: SidebarNavItem[] = NAV_ITEMS.filter((item) => !item.group).map(toItem);

  // Route changes were previously silent and untitled: document.title never changed, no
  // focus moved, and nothing was announced -- a screen-reader user got no signal the page
  // changed (SPEC.md §5.10). Every route shares one title/focus-management effect here
  // rather than duplicating it across each page. Focus (not just title) is skipped on the
  // very first render -- only subsequent, in-app navigations should steal focus from
  // wherever the browser naturally placed it on initial load.
  useEffect(() => {
    const current = NAV_ITEMS.find((item) => item.path === location.pathname);
    document.title = current
      ? `${current.label} — GHG Emissions Trend Analysis and Forecasting`
      : 'GHG Emissions Trend Analysis and Forecasting';
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [location.pathname]);

  return (
    <div
      data-theme="analytics"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        // Without this, the default content-box sizing adds the safe-area padding below
        // ON TOP of the 100vh minimum height, forcing unwanted vertical scroll in standalone
        // mode -- exactly the scenario this padding exists for. border-box keeps padding
        // inside the 100vh minimum instead.
        boxSizing: 'border-box',
        background: 'var(--__s9cmpx-static-background-weak)',
        // Only bites once installed standalone on iOS (index.html's apple-mobile-web-app-*
        // meta tags + viewport-fit=cover, SPEC.md §5.10) -- a plain Safari tab's own chrome
        // already absorbs the notch/home-indicator area, so this is a no-op there.
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
        paddingRight: 'env(safe-area-inset-right, 0px)',
      }}
    >
      {/* Visually hidden until focused (standard clip-based technique -- design-system has
          no existing utility class for this). Confirmed genuinely absent before this fix,
          not a false positive -- the only href="#" elements in this app are the sidebar nav
          items above, not a skip link. */}
      <a
        href="#main-content"
        style={{
          position: 'absolute',
          left: 8,
          top: 8,
          zIndex: 100,
          padding: '8px 16px',
          background: 'var(--__s9cmpx-static-background-standard)',
          color: 'var(--__s9cmpx-static-text-standard)',
          transform: 'translateY(-200%)',
        }}
        onFocus={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
        onBlur={(e) => (e.currentTarget.style.transform = 'translateY(-200%)')}
      >
        Skip to main content
      </a>
      <Header
        logo={
          <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.25, textAlign: 'left', minWidth: 0 }}>
            <span
              style={{
                fontSize: 'clamp(1rem, 4vw, 1.375rem)',
                fontWeight: 600,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              🌍 GHG Emissions Analysis
            </span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 400,
                color: 'var(--__s9cmpx-static-text-weak)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              IDEAS TIH Summer Internship 2026
            </span>
          </span>
        }
        searchPlaceholder=""
        showNotifications={false}
        showAppSwitcher={false}
        showUserMenu={false}
        style={{ minHeight: 68 }}
      />
      <div style={{ display: 'flex', flex: 1 }}>
        <SidebarNav
          groups={groups}
          footerItems={footerItems}
          mobileToggleSide="right"
          onItemClick={(id) => {
            const target = NAV_ITEMS.find((item) => item.id === id);
            if (target) navigate(target.path);
          }}
        />
        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          style={{
            flex: 1,
            background: 'var(--__s9cmpx-static-background-weak)',
            padding: 24,
            fontFamily: 'var(--__s9cmpx-font-families-primary)',
            color: 'var(--__s9cmpx-static-text-standard)',
          }}
        >
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/ask" element={<AgentPage />} />
            <Route path="/historical" element={<HistoricalTrendsPage />} />
            <Route path="/country-profile" element={<CountryProfilePage />} />
            <Route path="/forecasts" element={<ForecastsPage />} />
            <Route path="/scenarios" element={<ScenarioComparisonPage />} />
            <Route path="/data-explorer" element={<DataExplorerPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      {/* Footer's default `links` renders a "Policies" placeholder pointing at
          href="#" — this app has no policies page, so suppress it rather than
          ship a dead link. */}
      <Footer copyright="IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar" links={[]} />
      {/* Page-agnostic (SPEC.md §5.20), unlike JumpLinks -- wired once here rather than per page.
          targetId reuses the same #main-content landmark the route-change effect above already
          focuses on in-app navigation, so a back-to-top click lands focus in the same place.
          avoidSelector="footer" keeps the button docked above Footer's own <footer> element --
          reported directly, with screenshots: a JumpLinks target near the end of a short page can
          leave a large scrollable gap below the footer (the shortfall spacer scrollToJumpTarget
          uses, deliberately never auto-removed -- see its own comment), and without this the
          button rendered stranded deep inside that gap. */}
      <BackToTop targetId="main-content" avoidSelector="footer" />
    </div>
  );
}

export default App;
