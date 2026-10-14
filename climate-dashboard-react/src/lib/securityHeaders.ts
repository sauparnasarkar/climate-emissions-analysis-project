// The response headers the dashboard's own server sends, kept in the repo so the intended set is reviewable and tested rather than living
// only in a Cloudflare dashboard. They are the same values the edge's response-header rule sets (services/mcp-server/SPEC.md §8.2), so
// sending them from `vite preview` as well changes nothing in production -- it means a lost or edited edge rule no longer drops them.
//
// Content-Security-Policy is deliberately NOT here. A second CSP does not replace the edge's, it intersects with it, and this app's
// needs (Plotly's topojson from cdn.plot.ly, *.cloudflareaccess.com for the gated /admin fetch, cloudflareinsights.com) are only
// confirmed against the live edge policy. Required `connect-src` entries are recorded in ARCHITECTURE.md §5 instead.
export const SECURITY_HEADERS: Record<string, string> = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=(), usb=()',
}
