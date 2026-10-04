import { useEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Header, SidebarNav, Footer, BackToTop, useIsMobile } from 'design-system';
import type { SidebarNavItem, SidebarNavGroup } from 'design-system/components/SidebarNav/SidebarNav';

import type { AppTheme } from '../lib/theme';
import { AskAgentLink } from '../components/AskAgentLink';
import { MobileMenuButton } from '../components/MobileMenuButton';
import { ThemeToggle } from '../components/ThemeToggle';
import { useRouteAnnouncements } from '../hooks/useRouteAnnouncements';
import { FOOTER_COPYRIGHT, HOME_ITEM, NAV_ITEMS, PRODUCT_NAME } from '../navigation';

/** The dashboard shell (header, sidebar, footer, back-to-top) around every page under it; the
 * landing page at '/' uses LandingLayout instead. Theme state lives in App so both layouts share it. */
export function DashboardLayout({ theme, setTheme }: { theme: AppTheme; setTheme: (t: AppTheme) => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const mainRef = useRef<HTMLElement>(null);
  // Same 768px breakpoint SidebarNav itself switches on (design-system's own useIsMobile,
  // not a second hardcoded query) -- used below to stop rendering the theme toggle in the
  // header on mobile, where its grid track collapses and it has nowhere to render.
  const isMobile = useIsMobile();
  useRouteAnnouncements(mainRef);

  // Phone: the header's own "Menu" button (same as the landing header) opens SidebarNav's drawer, which is
  // controlled from here. Closed whenever we leave the phone layout or the route changes.
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => { if (!isMobile) setMenuOpen(false); }, [isMobile]);
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);

  const toItem = ({ path, group, ...item }: Omit<SidebarNavItem, 'active'> & { path: string; group?: string }): SidebarNavItem => ({
    ...item,
    href: path,
    active: location.pathname === path,
  });
  // Home sits alone in an unlabeled cluster above the labeled groups (Release 20, SPEC.md §5.25).
  const groups: SidebarNavGroup[] = [
    { items: [toItem(HOME_ITEM)] },
    ...(['Exploration', 'Projection'] as const).map((label) => ({
      label,
      items: NAV_ITEMS.filter((item) => item.group === label).map(toItem),
    })),
  ];
  const footerItems: SidebarNavItem[] = NAV_ITEMS.filter((item) => !item.group).map(toItem);

  // Shared between Header's rightActions (desktop) and SidebarNav's mobileOnlyContent (mobile
  // drawer) -- exactly one of the two ever actually renders it, gated by the same isMobile check
  // above, so there's only ever one theme toggle live in the DOM at a time.
  const themeToggle = <ThemeToggle theme={theme} setTheme={setTheme} />;

  return (
    <div
      data-theme={theme}
      className="app-shell"
      style={{
        display: 'flex',
        flexDirection: 'column',
        // 100vh fallback for browsers with no dvh support -- .app-shell's stylesheet rule below
        // overrides this with 100dvh wherever it's understood. Reported directly, with
        // screenshots: on iOS Safari, submitting a query disables (and therefore blurs) the
        // focused textarea, which dismisses the keyboard immediately rather than through the
        // OS's normal tap-away animation -- and 100vh is defined against the *largest* possible
        // viewport (URL bar collapsed), not whatever's currently visible, so WebKit's own
        // internal layout snapshot taken while the keyboard was still up doesn't get
        // recomputed on this abrupt a close. The result: a blank scrollable gap the height of
        // the vacated keyboard, persisting until something else forces reflow. 100dvh tracks
        // the actual visible viewport continuously instead, so it can't get stuck stale.
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
      {/* Inline styles can't express a fallback cascade for a single property the way a real
          stylesheet rule can -- an unsupported `100dvh` value here would just be dropped by
          React's style object, not fall back to `100vh` the way a second CSS declaration does. */}
      <style>{'.app-shell { min-height: 100dvh; }'}</style>
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
        className="app-header"
        logo={
          <span
            style={{
              display: 'flex',
              flexDirection: 'column',
              lineHeight: 1.25,
              textAlign: 'left',
              minWidth: 0,
              // On a phone the header's right slot holds the bordered "Menu" button (~96px wide), so cap the
              // title to leave it that room -- on a 320px phone (Galaxy S9+) a title with no cap painted
              // under the controls in an earlier layout. Harmless at wider widths: the title never gets
              // near this cap on a desktop viewport. 172px = 16px side padding x2, ~96px button, the header grid's
              // two 16px column gaps, and a little breathing room -- measured at 320px: with less, the grid
              // overflowed and pushed the button ~9px into the right padding.
              maxWidth: 'calc(100vw - 172px)',
            }}
          >
            <span
              style={{
                fontSize: 'clamp(1rem, 4vw, 1.375rem)',
                fontWeight: 600,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              🌍 {PRODUCT_NAME}
            </span>
          </span>
        }
        // Flush right, matching the landing header. Desktop: the theme toggle and "Ask the Agent". Phone
        // (below 768px, where there is no room for both): the bordered "Menu" button, exactly like the
        // landing header -- the toggle and Ask live inside the drawer it opens.
        rightActions={
          isMobile ? (
            <MobileMenuButton open={menuOpen} onClick={() => setMenuOpen((o) => !o)} />
          ) : (
            <>
              {themeToggle}
              <AskAgentLink />
            </>
          )
        }
        searchPlaceholder=""
        showNotifications={false}
        showAppSwitcher={false}
        showUserMenu={false}
        style={{ minHeight: 68 }}
      />
      <div style={{ display: 'flex', flex: 1 }}>
        <SidebarNav
          className="app-sidebar-nav"
          groups={groups}
          footerItems={footerItems}
          mobileToggleSide="right"
          onItemClick={(id) => {
            const target = [HOME_ITEM, ...NAV_ITEMS].find((item) => item.id === id);
            if (target) navigate(target.path);
          }}
          // Phone: the header's "Menu" button (above) drives this drawer, so SidebarNav's own floating menu
          // button and floating Ask action are switched off (hideMobileToggle) and both controls are offered
          // inside the drawer instead. Desktop: uncontrolled (the rail expands/collapses by itself).
          hideMobileToggle
          open={isMobile ? menuOpen : undefined}
          onToggle={(next) => { if (isMobile) setMenuOpen(next); }}
          mobileOnlyContent={
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12 }}>
              {themeToggle}
              <AskAgentLink />
            </div>
          }
        />
        <main
          id="main-content"
          ref={mainRef}
          tabIndex={-1}
          style={{
            flex: 1,
            // A flex child defaults to `min-width: auto` -- its own min-content width --
            // so it can never shrink below the widest thing inside it. On a 320px-wide
            // phone (Galaxy S9+) the Overview page's content floored this at 378px and
            // pushed the whole page into horizontal scroll; every page's charts and tables
            // reflow fine once the container is actually allowed to narrow.
            minWidth: 0,
            background: 'var(--__s9cmpx-static-background-weak)',
            padding: 24,
            fontFamily: 'var(--__s9cmpx-font-families-primary)',
            color: 'var(--__s9cmpx-static-text-standard)',
          }}
        >
            <Outlet />
        </main>
      </div>
      {/* Footer's default `links` renders a "Policies" placeholder pointing at
          href="#" — this app has no policies page, so suppress it rather than
          ship a dead link. */}
      <Footer copyright={FOOTER_COPYRIGHT} links={[]} />
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
