import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import 'design-system/styles/vendor/sy-design-system-reset.min.css'
import 'design-system/styles/vendor/syena-default-theme.css'
import 'design-system/styles/vendor/sy-design-system.min.css'
import 'design-system/styles/themes/analytics.css'

import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
