// Shared by vite.config.ts (Node, build-time) and main.tsx (browser, runtime) — the
// one invariant both need: "strip a single trailing slash, except the bare '/' case
// stays as '/'." Kept as one plain, dependency-free function so both can import it
// (Vite transpiles vite.config.ts's local imports the same as app code) instead of
// each re-deriving the same string operation independently.
export function stripTrailingSlash(path: string): string {
  return path === '/' ? '/' : path.replace(/\/$/, '');
}

export function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Paths the tunnel routes to *backends* (api/, services/mcp-server, services/agent) rather than to
// this SPA. At a prefixed base (labs.syena.io/ghg-emissions-analysis/) the service worker's scope
// was already narrow; at the root base of climate-analytics.syena.io (Release 20, SPEC.md §5.25) it
// covers the whole origin, so a top-level navigation to one of these (e.g. an Access login redirect
// on /agent/admin, or someone opening /api/health) must go to the network, not be answered with the
// SPA shell.
export const BACKEND_PATH_SEGMENTS = ['api', 'mcp', 'agent'] as const;

/** Workbox `navigateFallbackDenylist` patterns for a given base (with trailing slash): static files
 * (any path ending in an extension), the Access-gated /admin page, and every backend prefix. Workbox
 * tests these against `pathname + search`, hence the optional trailing query. */
export function navigateFallbackDenylist(base: string): RegExp[] {
  const b = escapeRegExp(base);
  const segment = (name: string) => new RegExp(`^${b}${name}(/[^?]*)?(\\?.*)?$`);
  return [/\.[a-zA-Z0-9]{2,5}(\?.*)?$/, segment('admin'), ...BACKEND_PATH_SEGMENTS.map(segment)];
}
