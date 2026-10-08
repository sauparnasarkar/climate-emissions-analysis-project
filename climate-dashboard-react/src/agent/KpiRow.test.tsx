import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { KpiRow } from './KpiRow';
import { formatKpiValue } from './kpiFormat';
import type { Kpi } from './types';

const k = (over: Partial<Kpi>): Kpi => ({ label: 'CO₂ emissions', value: 12289, unit: 'Mt', decimals: 0, year: 2024, sub: null, series: null, ...over });

describe('formatKpiValue', () => {
  it('formats each unit the way the handoff shows it', () => {
    expect(formatKpiValue(k({}))).toBe('12,289 Mt');
    expect(formatKpiValue(k({ value: 8.66, unit: 't', decimals: 2 }))).toBe('8.66 t');
    expect(formatKpiValue(k({ value: 1.68239, unit: '°C', decimals: 2 }))).toBe('1.68 °C');
    expect(formatKpiValue(k({ value: 1.0, unit: '%', decimals: 1 }))).toBe('+1.0%');
    expect(formatKpiValue(k({ value: -2.5, unit: '%', decimals: 1 }))).toBe('-2.5%');
  });
});

describe('KpiRow', () => {
  it('renders nothing for no KPIs', () => {
    const { container } = render(<KpiRow kpis={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('labels each card with its data year and shows the sub-line', () => {
    render(<KpiRow kpis={[k({ sub: 'Largest of 215 countries' }), k({ label: 'Per capita', value: 8.66, unit: 't', decimals: 2 })]} />);
    const list = screen.getByRole('list', { name: 'Key figures' });
    const cards = within(list).getAllByRole('listitem');
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveTextContent('CO₂ emissions · 2024');
    expect(cards[0]).toHaveTextContent('12,289 Mt');
    expect(cards[0]).toHaveTextContent('Largest of 215 countries');
    expect(cards[1]).toHaveTextContent('8.66 t');
  });

  it('gives a scenario card its pathway colour as a top border, and a plain card none', () => {
    render(<KpiRow kpis={[k({ label: 'BAU', series: 'BAU', value: 1.68, unit: '°C', decimals: 2 }), k({})]} />);
    const [bau, plain] = screen.getAllByRole('listitem');
    expect(bau.style.borderTop).toContain('3px solid');
    expect(plain.style.borderTop).toContain('1px solid');
  });
});
