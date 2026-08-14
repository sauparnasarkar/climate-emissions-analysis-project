import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WidgetRenderer } from './WidgetRenderer';
import type { WidgetSpec } from './types';

// Same convention as CountryProfilePage.test.tsx/OverviewPage.test.tsx -- Plotly's DOM
// lifecycle is design-system's own test suite's concern; stub SyChart down to its own props so
// this file's mapping logic (WidgetSpec.props -> SyChart series) is what's under test.
vi.mock('design-system', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  return {
    ...actual,
    SyChart: (props: { series: Array<{ name: string; kind?: string }> }) => (
      <div data-testid="sychart" data-series={JSON.stringify(props.series)} />
    ),
  };
});

function widget(overrides: Partial<WidgetSpec>): WidgetSpec {
  return {
    intent: 'text',
    chart_kind: null,
    title: 'Widget',
    as_of: null,
    source_tool_call: 'get_methodology_notes:{}',
    props: {},
    ...overrides,
  };
}

describe('WidgetRenderer', () => {
  it('renders get_historical_emissions as a line chart with one series per country', () => {
    const w = widget({
      intent: 'chart',
      chart_kind: 'line',
      source_tool_call: 'get_historical_emissions:{"countries":["China"]}',
      props: { gas_label: 'CO₂', series: [{ name: 'China', years: [2020, 2021], values: [100, 110] }] },
    });
    render(<WidgetRenderer widget={w} />);
    const series = JSON.parse(screen.getByTestId('sychart').dataset.series!);
    expect(series).toEqual([{ name: 'China', x: [2020, 2021], y: [100, 110], kind: 'line' }]);
  });

  it('renders get_top_emitters as bar with colorValues by default', () => {
    const w = widget({
      intent: 'chart',
      chart_kind: 'bar',
      source_tool_call: 'get_top_emitters:{}',
      props: { year: 2040, emitters: [{ country: 'China', iso_code: 'CHN', co2: 9000 }] },
    });
    render(<WidgetRenderer widget={w} />);
    const series = JSON.parse(screen.getByTestId('sychart').dataset.series!)[0];
    expect(series.kind).toBe('bar');
    expect(series.x).toEqual(['China']);
    expect(series.colorValues).toEqual([9000]);
  });

  it('renders get_top_emitters as a choropleth with locations (not iso_code) when chart_kind is choropleth', () => {
    const w = widget({
      intent: 'chart',
      chart_kind: 'choropleth',
      source_tool_call: 'get_top_emitters:{}',
      props: { year: 2024, emitters: [{ country: 'China', iso_code: 'CHN', co2: 9000 }] },
    });
    render(<WidgetRenderer widget={w} />);
    const series = JSON.parse(screen.getByTestId('sychart').dataset.series!)[0];
    expect(series.kind).toBe('choropleth');
    expect(series.locations).toEqual(['CHN']);
    expect(series).not.toHaveProperty('iso_code');
  });

  it('renders get_model_comparison as a titled grid Card without crashing on its columns/rows', () => {
    // AG Grid needs real layout measurements it never gets in jsdom (no ResizeObserver-driven
    // width), so -- same as every other DataTable-bearing page in this app -- cell content
    // isn't asserted here, only that the Card/header wiring from props.columns/rows is correct.
    const w = widget({
      intent: 'grid',
      title: 'Five-Model Comparison',
      source_tool_call: 'get_model_comparison:{}',
      props: { columns: ['model', 'mae'], rows: [{ model: 'ETS', mae: 12.3 }] },
    });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText('Five-Model Comparison')).toBeInTheDocument();
  });

  it('dispatches get_country_profile by widget.intent, not just source_tool_call, since both widgets share one source', () => {
    const source = 'get_country_profile:{"country":"China"}';
    const props = { years: [2020, 2021], co2: [100, null], co2_per_capita: [7.1, null], yoy_values: [5.2] };

    render(<WidgetRenderer widget={widget({ intent: 'card', source_tool_call: source, props })} />);
    expect(screen.getByText('CO₂ Emissions (Mt)')).toBeInTheDocument();
    expect(screen.queryByTestId('sychart')).not.toBeInTheDocument();

    render(<WidgetRenderer widget={widget({ intent: 'chart', chart_kind: 'line', source_tool_call: source, props })} />);
    expect(screen.getByTestId('sychart')).toBeInTheDocument();
  });

  it('renders get_country_profile card KpiStats from the last non-null value in each array', () => {
    const w = widget({
      intent: 'card',
      source_tool_call: 'get_country_profile:{}',
      props: { years: [2020, 2021, 2022], co2: [100, 110, null], co2_per_capita: [7, 7.5, null], yoy_values: [3.1, -2.4] },
    });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText('110')).toBeInTheDocument();
    expect(screen.getByText('-2.4%')).toBeInTheDocument();
  });

  it('renders get_methodology_notes as labeled text sections', () => {
    const w = widget({
      intent: 'text',
      source_tool_call: 'get_methodology_notes:{}',
      props: { forecasting_methodology: 'ETS(A,Ad,N) Holt damped trend.' },
    });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText('Forecasting Methodology')).toBeInTheDocument();
    expect(screen.getByText('ETS(A,Ad,N) Holt damped trend.')).toBeInTheDocument();
  });

  it('renders general_climate_node\'s fixed-literal source_tool_call as plain text, not the unrecognized-type fallback', () => {
    const w = widget({
      intent: 'text',
      source_tool_call: 'general_climate',
      title: 'Climate context',
      props: { text: 'CO2 is the primary driver of anthropogenic warming.' },
    });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText('CO2 is the primary driver of anthropogenic warming.')).toBeInTheDocument();
    expect(screen.queryByText(/recognized yet/)).not.toBeInTheDocument();
  });

  it('falls back to a warning for a tool ui_selection.py has no mapping for, without crashing', () => {
    const w = widget({ intent: 'card', source_tool_call: 'some_future_tool:{}', props: {} });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText(/recognized yet/)).toBeInTheDocument();
  });
});
