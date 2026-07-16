import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Header, SidebarNav, Footer } from 'design-system';
import type { SidebarNavItem } from 'design-system/components/SidebarNav/SidebarNav';

import OverviewPage from './pages/OverviewPage';
import HistoricalTrendsPage from './pages/HistoricalTrendsPage';
import CountryProfilePage from './pages/CountryProfilePage';
import ForecastsPage from './pages/ForecastsPage';
import ScenarioComparisonPage from './pages/ScenarioComparisonPage';
import AboutPage from './pages/AboutPage';

const NAV_ITEMS: Array<Omit<SidebarNavItem, 'active'> & { path: string }> = [
  { id: 'overview', label: 'Overview', icon: 'home', path: '/' },
  { id: 'historical', label: 'Historical Trends', icon: 'document', path: '/historical' },
  { id: 'country-profile', label: 'Country Profile', icon: 'user', path: '/country-profile' },
  { id: 'forecasts', label: 'Forecasts', icon: 'calendar', path: '/forecasts' },
  { id: 'scenarios', label: 'Scenario Comparison', icon: 'grid', path: '/scenarios' },
  { id: 'about', label: 'About', icon: 'info', path: '/about' },
];

function App() {
  const location = useLocation();
  const navigate = useNavigate();

  const items: SidebarNavItem[] = NAV_ITEMS.map(({ path, ...item }) => ({
    ...item,
    active: location.pathname === path,
  }));

  return (
    <div
      data-theme="analytics"
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        background: 'var(--sy-static-background-weak)',
      }}
    >
      <Header
        logo={
          <span style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.25, textAlign: 'left' }}>
            <span style={{ fontSize: '1.375rem', fontWeight: 600 }}>🌍 GHG Emissions Analysis</span>
            <span style={{ fontSize: '0.75rem', fontWeight: 400, color: 'var(--sy-static-text-weak)' }}>
              IDEAS TIH Summer Internship 2026
            </span>
          </span>
        }
        searchPlaceholder=""
        showNotifications={false}
        showAppSwitcher={false}
        showUserMenu={false}
        style={{ height: 'auto', minHeight: 68 }}
      />
      <div style={{ display: 'flex', flex: 1 }}>
        <SidebarNav
          items={items}
          mobileToggleSide="right"
          onItemClick={(id) => {
            const target = NAV_ITEMS.find((item) => item.id === id);
            if (target) navigate(target.path);
          }}
        />
        <main
          style={{
            flex: 1,
            background: 'var(--sy-static-background-weak)',
            padding: 24,
            fontFamily: 'var(--sy-font-families-primary)',
            color: 'var(--sy-static-text-standard)',
          }}
        >
          <Routes>
            <Route path="/" element={<OverviewPage />} />
            <Route path="/historical" element={<HistoricalTrendsPage />} />
            <Route path="/country-profile" element={<CountryProfilePage />} />
            <Route path="/forecasts" element={<ForecastsPage />} />
            <Route path="/scenarios" element={<ScenarioComparisonPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <Footer copyright="IDEAS TIH Summer Internship 2026 · Mentor: Sauparna Sarkar" />
    </div>
  );
}

export default App;
