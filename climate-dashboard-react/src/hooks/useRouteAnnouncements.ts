import { useEffect, type RefObject } from 'react';
import { useLocation } from 'react-router-dom';
import { APP_TITLE, HOME_ITEM, LANDING_TITLE, NAV_ITEMS } from '../navigation';

// Module-level (not a per-layout ref): the landing layout and the dashboard layout are separate
// mounts, so a per-layout "first render" flag would wrongly skip focus on the very first
// navigation *between* them. Only the app's genuine first paint should skip it.
let initialLoadDone = false;

/** Route changes were previously silent and untitled: document.title never changed, no focus
 * moved, and nothing was announced -- a screen-reader user got no signal the page changed
 * (SPEC.md §5.10). Every layout shares this one title/focus-management effect rather than
 * duplicating it. Focus (not just title) is skipped on the very first paint -- only later,
 * in-app navigations should steal focus from wherever the browser naturally placed it on load. */
export function useRouteAnnouncements(mainRef: RefObject<HTMLElement | null>) {
  const { pathname } = useLocation();
  useEffect(() => {
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
    mainRef.current?.focus();
  }, [pathname, mainRef]);
}
