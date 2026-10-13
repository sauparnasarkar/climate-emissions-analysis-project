/**
 * What a country share is a share of, by source (Release 24.0, ENHANCEMENTS.md decision 71). OWID shares are of the World total, which includes international
 * aviation and shipping, so a selection's "Rest of world" includes international transport; PRIMAP-hist has no world aggregate and excludes international
 * aviation and shipping, so its shares are of the sum of its own reporting areas and sum to 100%.
 */
export function shareBasis(source: string): { chip: string; footer: string } {
  if (source === 'primap_hist') {
    return {
      chip: "source's own total, bunkers excluded",
      footer: "denominator = the sum of PRIMAP-hist's reporting areas (it has no world aggregate and excludes international aviation and shipping), so its shares sum to 100% and are of that source's total, not of the World total.",
    };
  }
  return {
    chip: 'World total, bunkers included',
    footer: 'denominator = the World total, international aviation and shipping included (the same total as the dashboard’s cumulative views), so Rest of world includes international transport.',
  };
}
