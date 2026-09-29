import { describe, expect, it } from 'vitest';
import { navigateFallbackDenylist, stripTrailingSlash } from './basePath';

const denied = (base: string, url: string) => navigateFallbackDenylist(base).some((re) => re.test(url));

describe('stripTrailingSlash', () => {
  it('keeps the bare root and strips one trailing slash otherwise', () => {
    expect(stripTrailingSlash('/')).toBe('/');
    expect(stripTrailingSlash('/x/')).toBe('/x');
  });
});

describe('navigateFallbackDenylist', () => {
  it('at the root base (Release 20): sends backend prefixes, /admin and static files to the network', () => {
    for (const url of ['/api/health', '/api/overview?countries=China', '/mcp', '/agent/query', '/agent/admin/llm', '/admin', '/admin?x=1', '/about.pptx', '/sw.js?cachebust=1']) {
      expect(denied('/', url)).toBe(true);
    }
  });

  it('at the root base: leaves every SPA route on the shell fallback (including look-alikes)', () => {
    for (const url of ['/', '/overview', '/overview#pct-change', '/historical?countries=India', '/country-profile', '/ask', '/agentic', '/apis', '/mcp-notes', '/administrators']) {
      expect(denied('/', url)).toBe(false);
    }
  });

  it('at a prefixed base: the same rules apply under the prefix, not outside it', () => {
    const base = '/ghg-emissions-analysis/';
    expect(denied(base, '/ghg-emissions-analysis/agent/admin')).toBe(true);
    expect(denied(base, '/ghg-emissions-analysis/api/health')).toBe(true);
    expect(denied(base, '/ghg-emissions-analysis/overview')).toBe(false);
    expect(denied(base, '/agent/query')).toBe(false);
  });
});
