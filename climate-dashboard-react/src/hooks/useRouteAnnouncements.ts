import { useEffect, useRef, type RefObject } from 'react';
import { useLocation } from 'react-router-dom';
import { APP_TITLE, HOME_ITEM, LANDING_TITLE, NAV_ITEMS } from '../navigation';

// Module-level (not a per-layout ref): the landing layout and the dashboard layout are separate
// mounts, so a per-layout "first render" flag would wrongly skip focus on the very first
// navigation *between* them. Only the app's genuine first paint should skip it.
let initialLoadDone = false;
let lastHandledPathname: string | null = null;

/** Route changes were previously silent and untitled: document.title never changed, no focus
 * moved, and nothing was announced -- a screen-reader user got no signal the page changed
 * (SPEC.md §5.10). Every layout shares this one title/focus-management effect rather than
 * duplicating it. Focus (not just title) is skipped on the very first paint -- only later,
 * in-app navigations should steal focus from wherever the browser naturally placed it on load. */
export function useRouteAnnouncements(mainRef: RefObject<HTMLElement | null>) {
  const { pathname, hash } = useLocation();
  // Read inside the effect but deliberately not a dependency: a hash-only change on the same page
  // (a JumpLinks click) must not re-run the title/focus/scroll below.
  const hashRef = useRef(hash);
  hashRef.current = hash;
  useEffect(() => {
    if (pathname === lastHandledPathname) return;
    lastHandledPathname = pathname;

    if (pathname === HOME_ITEM.path) {
      document.title = LANDING_TITLE;
    } else {
      const current = NAV_ITEMS.find((item) => item.path === pathname);
      document.title = current ? `${current.label} — ${APP_TITLE}` : APP_TITLE;
    }
    if (!initialLoadDone) {
      initialLoadDone = true;
      return;
    }
    // preventScroll: scrolling is handled explicitly below, and focus() alone would scroll the page
    // to wherever it likes, racing the jump-to-hash hook.
    mainRef.current?.focus({ preventScroll: true });
    // React Router keeps the previous page's scroll offset across a route change (no
    // ScrollRestoration here), so following a link from far down the landing page used to open the
    // next page scrolled to (or clamped at) that same depth -- e.g. `/overview#pct-change` landed
    // mid-page instead of at the section. Start at the top; when the URL has a #hash, the page's
    // useJumpToHashOnLoad takes it from there once its content exists.
    if (!hashRef.current) window.scrollTo(0, 0);
  }, [pathname, mainRef]);
}
