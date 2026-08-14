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

  it('renders get_forecast_comparison, trimming trailing nulls from hist_co2 before joining to the forecast segment', () => {
    // Copilot's PR #144 review: a trailing null in hist_co2 right before the forecast segment
    // would otherwise create a visible gap in the line at the historical/forecast join.
    const w = widget({
      intent: 'chart',
      chart_kind: 'line',
      source_tool_call: 'get_forecast_comparison:{"countries":["China"]}',
      props: {
        forecasts: [
          { country: 'China', hist_years: [2016, 2017, 2018], hist_co2: [9000, 9500, null], forecast_years: [2019, 2020], forecast_mean: [10000, 10200] },
        ],
      },
    });
    render(<WidgetRenderer widget={w} />);
    const series = JSON.parse(screen.getByTestId('sychart').dataset.series!)[0];
    expect(series.x).toEqual([2016, 2017, 2019, 2020]);
    expect(series.y).toEqual([9000, 9500, 10000, 10200]);
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

  it('renders ui_selection_node\'s context_reuse tag (zero-tool-call turn) the same way as general_climate', () => {
    // SPEC.md correction #22: a turn that reused prior context instead of calling a new tool
    // gets its own distinct tag, not "general_climate" -- semantically different (this path did
    // reuse tool data at some point; general_climate never calls a tool at all) even though both
    // render identically as a single text widget.
    const w = widget({
      intent: 'text',
      source_tool_call: 'context_reuse',
      title: 'Answer',
      props: { text: "India's emissions have grown steadily." },
    });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText("India's emissions have grown steadily.")).toBeInTheDocument();
    expect(screen.queryByText(/recognized yet/)).not.toBeInTheDocument();
  });

  it('renders markdown -- headers, bold, and a GFM table -- as real elements, not raw syntax', () => {
    // Confirmed live: agent_node's own unconstrained answers (surfaced via the context_reuse
    // path above) routinely include headers/bold/tables for a detailed comparison, unlike
    // compose_response_node's plain-prose summaries -- raw '##'/'**'/'|---|' syntax showing up
    // as literal text reads as broken, not just unstyled.
    const markdown = [
      '## India vs. Peers',
      '',
      "**India** leads in relative growth.",
      '',
      '| Country | Growth |',
      '| --- | --- |',
      '| India | +452% |',
      '| China | +395% |',
    ].join('\n');
    const w = widget({ intent: 'text', source_tool_call: 'context_reuse', title: 'Answer', props: { text: markdown } });
    render(<WidgetRenderer widget={w} />);

    expect(screen.getByRole('heading', { name: 'India vs. Peers' })).toBeInTheDocument();
    expect(document.querySelector('strong')?.textContent).toBe('India');
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Growth' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '+452%' })).toBeInTheDocument();
    expect(screen.queryByText(/##|\*\*India\*\*/)).not.toBeInTheDocument();
  });

  it('falls back to a warning for a tool ui_selection.py has no mapping for, without crashing', () => {
    const w = widget({ intent: 'card', source_tool_call: 'some_future_tool:{}', props: {} });
    render(<WidgetRenderer widget={w} />);
    expect(screen.getByText(/recognized yet/)).toBeInTheDocument();
  });
});
