import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { BaselineChip } from './BaselineChip';
import { BaselineInfo, type BaselineSpec } from './BaselineInfo';
import { PurposeLine } from './PurposeLine';
import { SourceNote } from './SourceNote';
import { ALL_GAS_TAG, CAUSAL_CHAIN, FORCING_CONCEPT_ONLY, NO_COUNTRY_ATTRIBUTION, NOT_A_CLIMATE_MODEL, SCENARIO_LABEL } from '../../lib/climateCopy';

const spec: BaselineSpec = {
  baseline: '1990 = 100',
  reference: '1990 annual value',
  formula: 'value ÷ value₁₉₉₀ × 100',
  sourceRange: 'OWID, 1990–2024',
  excludedYears: 'None',
};

describe('BaselineChip', () => {
  it('renders "Baseline <x> · <source>" and omits the separator without a source', () => {
    const { rerender } = render(<BaselineChip baseline="1990" source="OWID" />);
    expect(screen.getByText('Baseline 1990 · OWID')).toBeInTheDocument();
    rerender(<BaselineChip baseline="1850–1900" />);
    expect(screen.getByText('Baseline 1850–1900')).toBeInTheDocument();
  });
});

describe('BaselineInfo', () => {
  it('starts closed and lists baseline, reference, formula, range and excluded years when opened (§2.5)', () => {
    render(<BaselineInfo spec={spec} label="Change since baseline" />);
    const button = screen.getByRole('button', { name: 'Baseline details: Change since baseline' });
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const panel = screen.getByRole('region', { name: 'Baseline for Change since baseline' });
    for (const text of ['Baseline', 'Reference', 'Formula', 'Source range', 'Excluded years', '1990 = 100', 'OWID, 1990–2024', 'None']) {
      expect(panel).toHaveTextContent(text);
    }
  });

  it('closes on Escape and on an outside click', () => {
    render(<div><BaselineInfo spec={spec} label="x" /><p>outside</p></div>);
    const button = screen.getByRole('button', { name: /baseline details/i });
    fireEvent.click(button);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
    fireEvent.click(button);
    fireEvent.mouseDown(screen.getByText('outside'));
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });
});

describe('PurposeLine and SourceNote', () => {
  it('prefix the purpose and list sources with an optional caveat', () => {
    render(<><PurposeLine>show the long-term relationship</PurposeLine><SourceNote sources={['OWID', 'Berkeley Earth']}>file of Jan 2025</SourceNote></>);
    expect(screen.getByText('Purpose:')).toBeInTheDocument();
    expect(screen.getByText(/Source: OWID · Berkeley Earth — file of Jan 2025/)).toBeInTheDocument();
  });

  it('a note on a chart panel (dark in every theme) takes the chart-surface muted colour, any other note the shared muted colour', () => {
    render(<><SourceNote sources={['A']} inChartPanel /><SourceNote sources={['B']} /></>);
    expect(screen.getByText(/Source: A/)).toHaveStyle({ color: 'var(--__s9cmpx-chart-surface-text-weak)' });
    expect(screen.getByText(/Source: B/)).toHaveStyle({ color: 'var(--__s9cmpx-static-text-weak)' });
  });
});

describe('climate copy guardrails', () => {
  it('keeps the four-step chain in order, forcing as concept only, and the all-gas view not called TCRE', () => {
    expect([...CAUSAL_CHAIN]).toEqual(['Emissions', 'Concentration', 'Radiative forcing', 'Temperature anomaly']);
    expect(FORCING_CONCEPT_ONLY).toMatch(/described here, not calculated/);
    expect(ALL_GAS_TAG).toMatch(/not TCRE/i);
  });

  it('never claims causation, attribution or a projection', () => {
    expect(NOT_A_CLIMATE_MODEL).toMatch(/not a climate model/);
    expect(NO_COUNTRY_ATTRIBUTION).toMatch(/no warming is attributed to a country/);
    expect(SCENARIO_LABEL).toMatch(/not projections/);
  });
});
