import { useEffect, useRef, type RefObject } from 'react';
import { useLocation } from 'react-router-dom';
import { APP_TITLE, HOME_ITEM, LANDING_TITLE, NAV_ITEMS } from '../navigation';

// Module-level (not a per-layout ref): the landing layout and the dashboard layout are separate
// mounts, so a per-layout "first render" flag would wrongly skip focus on the very first
// navigation *between* them. Only the app's genuine first paint should skip it.
let initialLoadDone = false;
let lastHandledPathname: string | null = null;

// Routes that are real pages but not navigation items; without an entry they fell back to the bare
// product name, so the Ask page's tab title was the same as the landing page's (ENHANCEMENTS.md Release 22).
const EXTRA_PAGE_LABELS: Record<string, string> = { '/ask': 'Ask the Agent', '/admin': 'Admin' };

const ANNOUNCER_ID = 'route-announcer';

/** The one polite live region route changes are announced through, appended to <body>. Created EMPTY on the
 * app's first paint and only updated afterwards: screen readers announce changes to a live region that already
 * exists, so creating it and filling it in the same tick would leave the first navigation of a session silent. */
function ensureAnnouncer(): HTMLElement {
  let el = document.getElementById(ANNOUNCER_ID);
  if (!el) {
    el = document.createElement('div');
    el.id = ANNOUNCER_ID;
    el.setAttribute('aria-live', 'polite');
    el.setAttribute('aria-atomic', 'true');
    // Clip-based visually-hidden (lib/visuallyHidden.ts, as a cssText since this node is outside React).
    el.style.cssText = 'position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0';
    document.body.appendChild(el);
  }
  return el;
}

/** Says the destination's name. The title change and the focus move are not announced consistently across
 * screen readers, and the only thing the pages' own live regions ever said after a navigation was "Loading…". */
function announce(label: string) {
  ensureAnnouncer().textContent = `${label} page`;
}

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
    ensureAnnouncer(); // exists (empty) before the first navigation, so that navigation is announced
    if (pathname === lastHandledPathname) return;
    lastHandledPathname = pathname;

    const isHome = pathname === HOME_ITEM.path;
    const pageLabel = isHome ? HOME_ITEM.label : NAV_ITEMS.find((item) => item.path === pathname)?.label ?? EXTRA_PAGE_LABELS[pathname];
    document.title = isHome ? LANDING_TITLE : pageLabel ? `${pageLabel} — ${APP_TITLE}` : APP_TITLE;
    if (!initialLoadDone) {
      initialLoadDone = true;
      return;
    }
    if (pageLabel) announce(pageLabel);
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
