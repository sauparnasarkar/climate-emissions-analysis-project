import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Set DEPLOY_BASE_PATH=/ghg-emissions-analysis/ when building/previewing for the
// Cloudflare Tunnel deployment (labs.syena.io/ghg-emissions-analysis). Defaults to
// root so local `npm run dev` / `npm run build` behavior is unchanged.
const base = process.env.DEPLOY_BASE_PATH || '/'

// vite preview 404s on the bare base path with no trailing slash (e.g. /ghg-emissions-analysis
// instead of /ghg-emissions-analysis/) rather than redirecting — a URL people will naturally
// type/share. Redirect it ourselves, before vite's own handling kicks in.
function redirectBareBasePlugin(base: string): Plugin {
  const bareBase = base.replace(/\/$/, '')
  return {
    name: 'redirect-bare-base-to-trailing-slash',
    configurePreviewServer(server) {
      server.middlewares.use((req, res, next) => {
        if (bareBase && req.url === bareBase) {
          res.statusCode = 301
          res.setHeader('Location', base)
          res.end()
          return
        }
        next()
      })
    },
  }
}

// Proxied under the same prefix as the app itself, matching how Cloudflare Tunnel
// forwards the full request path with no automatic prefix-stripping — the backend's
// own routes are mounted at plain /api/..., so strip `base` back off before forwarding.
const apiProxy = {
  target: 'http://localhost:8081',
  changeOrigin: true,
  rewrite: (p: string) => p.replace(base, '/'),
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), redirectBareBasePlugin(base)],
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
    proxy: {
      [`${base}api`]: apiProxy,
    },
  },
  preview: {
    port: 4173,
    proxy: {
      [`${base}api`]: apiProxy,
    },
    // Vite blocks unrecognized Host headers by default (DNS-rebinding protection) —
    // the Cloudflare Tunnel forwards requests with Host: labs.syena.io, which needs
    // an explicit allow. Only added when actually building for that deployment.
    allowedHosts: process.env.DEPLOY_BASE_PATH ? ['labs.syena.io'] : undefined,
  },
})
