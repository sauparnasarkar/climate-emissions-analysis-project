import { useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { Footer, BackToTop, useIsMobile } from 'design-system';

import type { AppTheme } from '../lib/theme';
import { AskAgentLink } from '../components/AskAgentLink';
import { MobileMenuButton } from '../components/MobileMenuButton';
import { ThemeToggle } from '../components/ThemeToggle';
import { PHONE_LANDSCAPE_QUERY, TABLET_QUERY, useMediaQuery } from '../hooks/useMediaQuery';
import { useRouteAnnouncements } from '../hooks/useRouteAnnouncements';
import { FOOTER_COPYRIGHT, LANDING_NAV_FOOTER_IDS, NAV_ITEMS, PRODUCT_NAME } from '../navigation';

const linkStyle = { color: 'inherit', textDecoration: 'none', fontSize: 14 } as const;

/** Layout for the landing page at '/' (Release 20, SPEC.md §5.25): a top nav instead of the
 * dashboard's sidebar, using the app's exact nav labels. Below 768px (same breakpoint as
 * SidebarNav, via design-system's own useIsMobile) the nav collapses behind a menu button. */
export function LandingLayout({ theme, setTheme }: { theme: AppTheme; setTheme: (t: AppTheme) => void }) {
  const mainRef = useRef<HTMLElement>(null);
  // Portrait or landscape, a phone gets the same compact header (decision 74): narrow screens (useIsMobile) and phones turned sideways. A tablet gets it too, below the width where the six nav links no longer fit on one line.
  // Both hooks run on every render (a `||` would skip the second while the first is true, and rotating the phone would change the hook count).
  const narrow = useIsMobile();
  const landscapePhone = useMediaQuery(PHONE_LANDSCAPE_QUERY);
  const tablet = useMediaQuery(TABLET_QUERY);
  const isMobile = narrow || landscapePhone || tablet;
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

  // Desktop top nav omits the pages the footer carries; the phone menu below lists them all.
  const topNavItems = NAV_ITEMS.filter((item) => !(LANDING_NAV_FOOTER_IDS as readonly string[]).includes(item.id));
  const footerLinks = NAV_ITEMS.filter((item) => (LANDING_NAV_FOOTER_IDS as readonly string[]).includes(item.id)).map((item) => ({
    label: item.label,
    // Footer renders plain anchors, not router Links, so the base path (basename) is added here.
    href: `${import.meta.env.BASE_URL}${item.path.slice(1)}`,
  }));
  const navLinks = topNavItems.map((item) => (
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
          <span aria-hidden="true">🌍</span> {PRODUCT_NAME}
        </Link>
        {isMobile ? (
          <div style={{ marginLeft: 'auto' }}>
            <MobileMenuButton open={menuOpen} onClick={() => setMenuOpen((o) => !o)} controls="landing-menu" />
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
      <Footer copyright={FOOTER_COPYRIGHT} links={footerLinks} />
      <BackToTop targetId="main-content" avoidSelector="footer" />
    </div>
  );
}
