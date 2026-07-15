import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Set DEPLOY_BASE_PATH=/ghg-emissions-analysis/ when building/previewing for the
  // Cloudflare Tunnel deployment (labs.syena.io/ghg-emissions-analysis). Defaults to
  // root so local `npm run dev` / `npm run build` behavior is unchanged.
  base: process.env.DEPLOY_BASE_PATH || '/',
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
      '/api': 'http://localhost:8081',
    },
  },
})
