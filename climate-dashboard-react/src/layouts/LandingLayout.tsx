import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Footer, BackToTop, Icon, useIsMobile } from 'design-system';

import type { AppTheme } from '../lib/theme';
import { AskAgentLink } from '../components/AskAgentLink';
import { ThemeToggle } from '../components/ThemeToggle';
import { useRouteAnnouncements } from '../hooks/useRouteAnnouncements';
import { NAV_ITEMS } from '../navigation';

const linkStyle = { color: 'inherit', textDecoration: 'none', fontSize: 14 } as const;

/** Layout for the landing page at '/' (Release 20, SPEC.md §5.25): a top nav instead of the
 * dashboard's sidebar, using the app's exact nav labels. Below 768px (same breakpoint as
 * SidebarNav, via design-system's own useIsMobile) the nav collapses behind a menu button. */
export function LandingLayout({ theme, setTheme }: { theme: AppTheme; setTheme: (t: AppTheme) => void }) {
  const mainRef = useRef<HTMLElement>(null);
  const isMobile = useIsMobile();
  const [menuOpen, setMenuOpen] = useState(false);
  const { pathname } = useLocation();
  useRouteAnnouncements(mainRef);

  // Close the menu on navigation, and on Escape.
  useEffect(() => setMenuOpen(false), [pathname]);
  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMenuOpen(false);
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [menuOpen]);

  const navLinks = NAV_ITEMS.map((item) => (
    <Link key={item.id} to={item.path} style={linkStyle}>{item.label}</Link>
  ));
  const askLink = <AskAgentLink />;


  return (
    <div
      data-theme={theme}
      className="app-shell"
      style={{
        display: 'flex',
        flexDirection: 'column',
        // 100dvh (via the .app-shell rule below) tracks the visible viewport; 100vh is the fallback
        // -- same reasoning as DashboardLayout's shell.
        minHeight: '100vh',
        boxSizing: 'border-box',
        background: 'var(--__s9cmpx-static-background-weak)',
        color: 'var(--__s9cmpx-static-text-standard)',
        fontFamily: 'var(--__s9cmpx-font-families-primary)',
        paddingTop: 'env(safe-area-inset-top, 0px)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        paddingLeft: 'env(safe-area-inset-left, 0px)',
        paddingRight: 'env(safe-area-inset-right, 0px)',
      }}
    >
      <style>{'.app-shell { min-height: 100dvh; }'}</style>
      <a
        href="#main-content"
        style={{
          position: 'absolute', left: 8, top: 8, zIndex: 100, padding: '8px 16px',
          background: 'var(--__s9cmpx-static-background-standard)', color: 'var(--__s9cmpx-static-text-standard)',
          transform: 'translateY(-200%)',
        }}
        onFocus={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
        onBlur={(e) => (e.currentTarget.style.transform = 'translateY(-200%)')}
      >
        Skip to main content
      </a>
      <header
        style={{
          position: 'relative', display: 'flex', alignItems: 'center', gap: 24, minHeight: 68, boxSizing: 'border-box',
          padding: isMobile ? '0 16px' : '0 clamp(16px, 5.5vw, 80px)',
          background: 'var(--__s9cmpx-static-background-standard)',
          borderBottom: '1px solid var(--__s9cmpx-static-divider-weak)',
        }}
      >
        <Link to="/" style={{ ...linkStyle, display: 'flex', alignItems: 'center', gap: 10, fontWeight: 600, fontSize: 'clamp(1rem, 4vw, 1.0625rem)' }}>
          <span aria-hidden="true">🌍</span> GHG Emissions Analytics
        </Link>
        {isMobile ? (
          <div style={{ marginLeft: 'auto' }}>
            <button
              type="button"
              aria-expanded={menuOpen}
              aria-controls="landing-menu"
              onClick={() => setMenuOpen((o) => !o)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: 44, padding: '0 12px', background: 'transparent', color: 'inherit', border: '1px solid var(--__s9cmpx-static-divider-standard)', borderRadius: 8, cursor: 'pointer', font: 'inherit' }}
            >
              <Icon name={menuOpen ? 'close' : 'menu'} size={18} />
              Menu
            </button>
            {menuOpen && (
              <nav
                id="landing-menu"
                aria-label="Primary"
                style={{
                  position: 'absolute', left: 0, right: 0, top: '100%', zIndex: 50, display: 'flex', flexDirection: 'column', gap: 4, padding: 16,
                  background: 'var(--__s9cmpx-static-background-standard)', borderBottom: '1px solid var(--__s9cmpx-static-divider-weak)',
                }}
              >
                {NAV_ITEMS.map((item) => (
                  <Link key={item.id} to={item.path} style={{ ...linkStyle, padding: '12px 4px', fontSize: 16 }}>{item.label}</Link>
                ))}
                <div style={{ display: 'flex', gap: 12, alignItems: 'center', paddingTop: 12, flexWrap: 'wrap' }}>
                  <ThemeToggle theme={theme} setTheme={setTheme} />
                  {askLink}
                </div>
              </nav>
            )}
          </div>
        ) : (
          <>
            <nav aria-label="Primary" style={{ display: 'flex', flexWrap: 'wrap', gap: 24 }}>{navLinks}</nav>
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
              <ThemeToggle theme={theme} setTheme={setTheme} />
              {askLink}
            </div>
          </>
        )}
      </header>
      <main id="main-content" ref={mainRef} tabIndex={-1} style={{ flex: 1, minWidth: 0 }}>
        <Outlet />
      </main>
      <Footer copyright="Greenhouse Gas Emissions Analytics Platform · Sauparna Sarkar" links={[]} />
      <BackToTop targetId="main-content" avoidSelector="footer" />
    </div>
  );
}
