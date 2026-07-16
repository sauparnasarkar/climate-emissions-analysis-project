// Shared by vite.config.ts (Node, build-time) and main.tsx (browser, runtime) — the
// one invariant both need: "strip a single trailing slash, except the bare '/' case
// stays as '/'." Kept as one plain, dependency-free function so both can import it
// (Vite transpiles vite.config.ts's local imports the same as app code) instead of
// each re-deriving the same string operation independently.
export function stripTrailingSlash(path: string): string {
  return path === '/' ? '/' : path.replace(/\/$/, '');
}
