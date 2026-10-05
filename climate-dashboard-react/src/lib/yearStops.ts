/**
 * Autoplay/jump stops over a year range: `minYear`, then every `stepYears`-year boundary after it, then `maxYear` (if it isn't already
 * one of those boundaries). For 1970–2024 in tens: 1970, 1980, 1990, 2000, 2010, 2020, 2024 (requirements §2.6). Year-over-year change is
 * gradual enough that stepping through every year hides the trend; jumping by decade makes it obvious at a glance.
 */
export function computeAutoplayStops(minYear: number, maxYear: number, stepYears: number): number[] {
  const stops = [minYear];
  for (let year = Math.ceil((minYear + 1) / stepYears) * stepYears; year < maxYear; year += stepYears) {
    stops.push(year);
  }
  if (stops[stops.length - 1] !== maxYear) stops.push(maxYear);
  return stops;
}
