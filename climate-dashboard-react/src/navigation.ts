import type { SidebarNavItem } from 'design-system/components/SidebarNav/SidebarNav';

// `group` is omitted for About, which is meta-content pinned to the sidebar's existing
// footerItems slot rather than clustered with either group.
// services/agent's conversational agent (SPEC.md §1-§2) is no longer a NAV_ITEMS entry -- it's a
// SidebarNav.persistentAction instead (direct instruction: "persistent, always-visible action"
// next to the menu toggle, not one page among the others in the list). See the SidebarNav render
// below for its wiring; the '/ask' route itself is unchanged, still registered in <Routes>.
// Release 21 Area 2 ships page by page (ENHANCEMENTS.md "Section 2 plan"). Until the whole module is
// ready, its nav entry is hidden from production builds -- the route itself always exists -- so a
// deploy of an early step never exposes a half-built page. Dev/test builds show it; production
// builds opt in with VITE_AREA2_ENABLED=true. The last step of the sequence removes this gate.
export const AREA2_ENABLED = import.meta.env.DEV || import.meta.env.VITE_AREA2_ENABLED === 'true';

const ALL_NAV_ITEMS: Array<Omit<SidebarNavItem, 'active'> & { path: string; group?: 'Exploration' | 'Projection' }> = [
  { id: 'overview', label: 'Overview', icon: 'home', path: '/overview', group: 'Exploration' },
  { id: 'historical', label: 'Historical Trends', icon: 'document', path: '/historical', group: 'Exploration' },
  { id: 'country-profile', label: 'Country Profile', icon: 'user', path: '/country-profile', group: 'Exploration' },
  { id: 'data-explorer', label: 'Data Explorer', icon: 'search', path: '/data-explorer', group: 'Exploration' },
  // Release 21 Area 2 (ENHANCEMENTS.md decision 57). Placeholder icon until design-system has a chart glyph.
  { id: 'climate-correlation', label: 'Climate Correlation', icon: 'sparkle', path: '/climate-correlation', group: 'Exploration' },
  { id: 'forecasts', label: 'Forecasts', icon: 'calendar', path: '/forecasts', group: 'Projection' },
  { id: 'scenarios', label: 'Scenario Comparison', icon: 'grid', path: '/scenarios', group: 'Projection' },
  { id: 'about', label: 'About', icon: 'info', path: '/about' },
];

export const NAV_ITEMS = ALL_NAV_ITEMS.filter((item) => AREA2_ENABLED || item.id !== 'climate-correlation');

// The landing page (Release 20, SPEC.md §5.25) lives at '/'. Deliberately not in NAV_ITEMS: it has
// no group, isn't a dashboard page, and the sidebar renders it as its own unlabeled cluster above
// the Exploration group rather than beside About in the footer.
export const HOME_ITEM: Omit<SidebarNavItem, 'active'> & { path: string } = { id: 'home', label: 'Home', icon: 'globe', path: '/' };

// Release 21 (ENHANCEMENTS.md decision 58): one product name everywhere.
export const PRODUCT_NAME = 'Climate Analytics Platform';
export const APP_TITLE = PRODUCT_NAME;
export const LANDING_TITLE = PRODUCT_NAME;
export const FOOTER_COPYRIGHT = `${PRODUCT_NAME} · Sauparna Sarkar`;

// The landing top nav fits one line at 1280px by leaving these two to the footer and (below 768px)
// the menu, which still lists every page (Area 2 design, L1 SPEC NOTES "Nav").
export const LANDING_NAV_FOOTER_IDS = ['data-explorer', 'about'] as const;
