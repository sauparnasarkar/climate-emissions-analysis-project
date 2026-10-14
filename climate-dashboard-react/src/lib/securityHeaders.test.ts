import { describe, expect, it } from 'vitest'
import { SECURITY_HEADERS } from './securityHeaders'

describe('SECURITY_HEADERS', () => {
  it('carries the set the edge rule documents, with nothing that could intersect the edge CSP', () => {
    expect(SECURITY_HEADERS).toMatchObject({
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'strict-origin-when-cross-origin',
    })
    expect(Object.keys(SECURITY_HEADERS).map((h) => h.toLowerCase())).not.toContain('content-security-policy')
  })

  it('switches off the powerful browser features this app never uses', () => {
    for (const feature of ['camera', 'microphone', 'geolocation']) expect(SECURITY_HEADERS['Permissions-Policy']).toContain(`${feature}=()`)
  })
})
