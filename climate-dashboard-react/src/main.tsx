import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import 'design-system/styles/vendor/sy-design-system-reset.min.css'
import 'design-system/styles/vendor/syena-default-theme.css'
import 'design-system/styles/vendor/sy-design-system.min.css'
import 'design-system/styles/themes/analytics.css'

import App from './App.tsx'

// Vite's BASE_URL always has a trailing slash; react-router's basename should not
// (except for the bare "/" root case).
const basename = import.meta.env.BASE_URL === '/' ? '/' : import.meta.env.BASE_URL.replace(/\/$/, '')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter basename={basename}>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
