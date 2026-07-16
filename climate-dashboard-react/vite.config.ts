import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
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

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

// PWA manifest colors match the app shell's own background tokens
// (App.tsx's --sy-static-background-weak) — not redeclared here since the
// theme CSS isn't parsed at build time, so keep these two in sync by hand if
// the analytics theme's background token ever changes.
const APP_BACKGROUND = '#121e35'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    redirectBareBasePlugin(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'GHG Emissions Trend Analysis and Forecasting',
        short_name: 'GHG Emissions',
        description: 'An end-to-end analysis of greenhouse gas emissions for 10 major countries using the OWID CO₂ dataset, regression models, and ETS(A,Ad,N) forecasting.',
        theme_color: APP_BACKGROUND,
        background_color: APP_BACKGROUND,
        display: 'standalone',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          // Same source image reused for the maskable slot — it already has generous
          // padding around the mark, so it clears Android's 80% safe-zone circle
          // without needing a separately-authored asset. Without at least one
          // maskable icon, Android's adaptive-icon shell adds its own default
          // background, clashing with the dark #121e35 shell.
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // The main JS bundle is ~6MB unminified (pre-existing — this app isn't
        // code-split yet, a separate concern from PWA setup) and exceeds
        // Workbox's 2MB default precache ceiling. Raised with headroom rather
        // than blocking PWA support on an unrelated bundle-splitting project.
        maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
        // Data freshness matters more than offline access for a live emissions
        // dashboard — go to the network first for API calls (short timeout
        // before falling back to any cached copy), and let Workbox's default
        // precache-then-serve behavior handle the built JS/CSS/icons as-is.
        runtimeCaching: [
          {
            // A regex literal, not a function closing over `base` — vite-plugin-pwa
            // serializes this urlPattern into the standalone sw.js file as a string;
            // a function referencing an outer build-time variable ships with that
            // identifier intact but nothing to resolve it against in the service
            // worker's own JS context, throwing "ReferenceError: base is not defined"
            // on every single fetch event once the worker actually controls a page.
            // Confirmed via a real browser's Service Worker console (not caught by
            // any of this session's automated testing — a worker only controls a
            // page from its *second* load onward, which fresh single-load test
            // contexts never reach). A regex's value is `base` baked in as a plain
            // string at build time, with nothing left to resolve at runtime.
            urlPattern: new RegExp(`^${escapeRegExp(base)}api/`),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              networkTimeoutSeconds: 5,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
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
