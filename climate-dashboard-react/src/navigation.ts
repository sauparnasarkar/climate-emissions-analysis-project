import type { SidebarNavItem } from 'design-system/components/SidebarNav/SidebarNav';

// `group` is omitted for About, which is meta-content pinned to the sidebar's existing
// footerItems slot rather than clustered with either group.
// services/agent's conversational agent (SPEC.md §1-§2) is no longer a NAV_ITEMS entry -- it's a
// SidebarNav.persistentAction instead (direct instruction: "persistent, always-visible action"
// next to the menu toggle, not one page among the others in the list). See the SidebarNav render
// below for its wiring; the '/ask' route itself is unchanged, still registered in <Routes>.
export const NAV_ITEMS: Array<Omit<SidebarNavItem, 'active'> & { path: string; group?: 'Exploration' | 'Projection' }> = [
  { id: 'overview', label: 'Overview', icon: 'home', path: '/overview', group: 'Exploration' },
  { id: 'historical', label: 'Historical Trends', icon: 'document', path: '/historical', group: 'Exploration' },
  { id: 'country-profile', label: 'Country Profile', icon: 'user', path: '/country-profile', group: 'Exploration' },
  { id: 'data-explorer', label: 'Data Explorer', icon: 'search', path: '/data-explorer', group: 'Exploration' },
  { id: 'forecasts', label: 'Forecasts', icon: 'calendar', path: '/forecasts', group: 'Projection' },
  { id: 'scenarios', label: 'Scenario Comparison', icon: 'grid', path: '/scenarios', group: 'Projection' },
  { id: 'about', label: 'About', icon: 'info', path: '/about' },
];

// The landing page (Release 20, SPEC.md §5.25) lives at '/'. Deliberately not in NAV_ITEMS: it has
// no group, isn't a dashboard page, and the sidebar renders it as its own unlabeled cluster above
// the Exploration group rather than beside About in the footer.
export const HOME_ITEM: Omit<SidebarNavItem, 'active'> & { path: string } = { id: 'home', label: 'Home', icon: 'globe', path: '/' };

export const APP_TITLE = 'GHG Emissions Trend Analysis and Forecasting';
export const LANDING_TITLE = 'GHG Emissions Analytics';
