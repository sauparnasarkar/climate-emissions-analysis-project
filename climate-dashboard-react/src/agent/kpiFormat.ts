import type { Kpi } from './types';

/** "12,289 Mt", "8.66 t", "+1.0%", "1.68 °C": the value to its stated decimals, signed for a percentage change. */
export function formatKpiValue(kpi: Pick<Kpi, 'value' | 'unit' | 'decimals'>): string {
  const n = kpi.value.toLocaleString(undefined, { minimumFractionDigits: kpi.decimals, maximumFractionDigits: kpi.decimals });
  if (kpi.unit === '%') return `${kpi.value > 0 ? '+' : ''}${n}%`;
  return kpi.unit ? `${n} ${kpi.unit}` : n;
}
