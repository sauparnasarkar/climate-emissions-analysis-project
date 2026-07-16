import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { stripTrailingSlash } from './src/lib/basePath.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Set DEPLOY_BASE_PATH=/ghg-emissions-analysis/ when building/previewing for the
// Cloudflare Tunnel deployment (labs.syena.io/ghg-emissions-analysis). Defaults to
// root so local `npm run dev` / `npm run build` behavior is unchanged. Normalized so a
// value given without leading/trailing slashes (or with only one, or nothing but
// slashes) can't produce a malformed base/proxy key downstream.
function normalizeBase(raw: string | undefined): string {
  const stripped = (raw ?? '').replace(/^\/+|\/+$/g, '')
  return stripped ? `/${stripped}/` : '/'
}
const base = normalizeBase(process.env.DEPLOY_BASE_PATH)
const bareBase = stripTrailingSlash(base)
const isPrefixed = base !== '/'

// vite preview 404s on the bare base path with no trailing slash (e.g. /ghg-emissions-analysis
// instead of /ghg-emissions-analysis/) rather than redirecting — a URL people will naturally
// type/share. Redirect it ourselves, before vite's own handling kicks in. Applied to both
// `vite dev` and `vite preview` so the two modes behave identically if DEPLOY_BASE_PATH is
// ever set for local dev too.
function redirectBareBasePlugin(): Plugin {
  const middleware = (req: IncomingMessage, res: ServerResponse, next: () => void) => {
    if (!isPrefixed || !req.url) return next()
    // Compare against the pathname only — req.url includes the query string,
    // and a URL like /ghg-emissions-analysis?utm_source=x is exactly the kind
    // of link people share, so it needs to redirect too (preserving the query).
    const queryIndex = req.url.indexOf('?')
    const pathname = queryIndex === -1 ? req.url : req.url.slice(0, queryIndex)
    if (pathname === bareBase) {
      const query = queryIndex === -1 ? '' : req.url.slice(queryIndex)
      res.statusCode = 301
      res.setHeader('Location', base + query)
      res.end()
      return
    }
    next()
  }
  return {
    name: 'redirect-bare-base-to-trailing-slash',
    configureServer(server) {
      server.middlewares.use(middleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use(middleware)
    },
  }
}

// Proxied under the same prefix as the app itself, matching how Cloudflare Tunnel
// forwards the full request path with no automatic prefix-stripping — the backend's
// own routes are mounted at plain /api/..., so strip `base` back off before forwarding.
const apiProxy = {
  target: 'http://localhost:8081',
  changeOrigin: true,
  // Anchored to the leading prefix specifically — a plain p.replace(base, '/') would
  // rewrite the *first* occurrence of `base` anywhere in the path, not necessarily
  // the leading one.
  rewrite: (p: string) => (p.startsWith(base) ? p.slice(base.length - 1) : p),
}

const apiProxyEntry = { [`${base}api`]: apiProxy }

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), redirectBareBasePlugin()],
  base,
  resolve: {
    alias: {
      // design-system has no main/exports/dist — alias straight to its source so
      // Vite treats it as part of this app's own module graph (same as its Storybook does).
      // design-system is a separate sibling-of-the-monorepo project (shared across other
      // apps too), so it lives one level further up than the rest of this repo.
      'design-system': path.resolve(__dirname, '../../design-system/src'),
      // Since design-system's components run inside this app's bundle (not a separate
      // installed package), react/react-dom must resolve to a single copy or hooks break.
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
  },
  server: {
    port: 5173,
    proxy: apiProxyEntry,
  },
  preview: {
    port: 4173,
    proxy: apiProxyEntry,
    // Vite blocks unrecognized Host headers by default (DNS-rebinding protection) —
    // the Cloudflare Tunnel forwards requests with Host: labs.syena.io, which needs
    // an explicit allow. Gated on the *normalized* base (not the raw env var) so
    // e.g. DEPLOY_BASE_PATH=/ (which normalizes to root) doesn't unexpectedly
    // restrict preview access even though it isn't really a prefixed deploy.
    allowedHosts: isPrefixed ? ['labs.syena.io'] : undefined,
  },
})
