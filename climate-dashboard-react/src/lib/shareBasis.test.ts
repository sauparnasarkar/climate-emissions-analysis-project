import { describe, expect, it } from 'vitest';
import { shareBasis } from './shareBasis';

describe('shareBasis', () => {
  it('OWID shares are of the World total with bunkers included; Rest of world then includes international transport', () => {
    const b = shareBasis('owid_co2');
    expect(b.chip).toBe('World total, bunkers included');
    expect(b.footer).toContain('World total, international aviation and shipping included');
    expect(b.footer).toContain('Rest of world includes international transport');
    expect(b.footer).not.toContain('national sum');
  });

  it("PRIMAP-hist shares are of the source's own total: no world aggregate, bunkers excluded, sums to 100%", () => {
    const b = shareBasis('primap_hist');
    expect(b.chip).toBe("source's own total, bunkers excluded");
    expect(b.footer).toContain('no world aggregate');
    expect(b.footer).toContain('sum to 100%');
    expect(b.footer).toContain('not of the World total');
  });
});
