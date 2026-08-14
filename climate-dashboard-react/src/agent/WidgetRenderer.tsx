import type { ComponentProps, ReactElement } from 'react';
import type { ColDef } from 'ag-grid-community';
import { Card, CardHeader, ChartCard, DataTable, InlineAlert, KpiStat, SyChart } from 'design-system';
import { toolNameFromSourceTaggedCall } from './types';
import type { WidgetSpec } from './types';

// Maps each WidgetSpec to its real design-system prop shape (SPEC.md §3/§3.1), keyed on the
// tool that produced it -- widget.props carries each tool's raw MCP result through unshaped
// (SPEC.md "Corrections applied" #9), so this is the one place that knows every real tool's
// response shape (cross-referenced against api/schemas.py and services/mcp-server/src/
// mcp_server/tools/*.py, not guessed). widget.source_tool_call is `${tool_name}:${json args}`
// (cache.py's cache_key) -- toolNameFromSourceTaggedCall recovers the tool name from it.

// design-system's index.ts doesn't re-export SyChartSeries (only the SyChart component itself,
// same as every existing page in this app, none of which import that type either -- they build
// inline series literals and let SyChart's own prop type check them structurally). Derived via
// ComponentProps rather than adding a design-system export for a single-app frontend PR.
type SyChartSeries = ComponentProps<typeof SyChart>['series'][number];

function humanize(field: string): string {
  return field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function genericColumns(rows: Record<string, unknown>[]): ColDef<Record<string, unknown>>[] {
  const keys = rows.length > 0 ? Object.keys(rows[0]) : [];
  return keys.map((field) => ({ field, headerName: humanize(field) }));
}

function lastDefined<T>(values: T[]): T | undefined {
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] != null) return values[i];
  }
  return undefined;
}

interface WidgetProps {
  widget: WidgetSpec;
}

function ChartWidget({ title, asOf, series, xTitle, yTitle, ariaLabel }: { title: string; asOf?: string | null; series: SyChartSeries[]; xTitle?: string; yTitle?: string; ariaLabel?: string }) {
  return (
    <ChartCard title={title} asOf={asOf ?? undefined}>
      <SyChart series={series} xTitle={xTitle} yTitle={yTitle} ariaLabel={ariaLabel} />
    </ChartCard>
  );
}

function GridWidget({ title, columns, rows }: { title: string; columns: ColDef<Record<string, unknown>>[]; rows: Record<string, unknown>[] }) {
  return (
    <Card header={<CardHeader title={title} />}>
      <DataTable columns={columns} rows={rows} />
    </Card>
  );
}

function HistoricalEmissionsWidget({ widget }: WidgetProps) {
  const props = widget.props as { gas_label?: string; series?: Array<{ name: string; years: number[]; values: Array<number | null> }> };
  const series: SyChartSeries[] = (props.series ?? []).map((s) => ({ name: s.name, x: s.years, y: s.values, kind: 'line' }));
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle={props.gas_label ?? 'CO₂ (Mt)'} />;
}

function ScenarioProjectionWidget({ widget }: WidgetProps) {
  const props = widget.props as {
    historical?: { name: string; years: number[]; values: number[] } | null;
    scenarios?: Array<{ name: string; years: number[]; values: number[] }>;
  };
  const series: SyChartSeries[] = [
    ...(props.historical ? [{ name: props.historical.name, x: props.historical.years, y: props.historical.values, kind: 'line' as const }] : []),
    ...(props.scenarios ?? []).map((s) => ({ name: s.name, x: s.years, y: s.values, kind: 'line' as const })),
  ];
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle="CO₂ (Mt)" />;
}

function CompareScenariosWidget({ widget }: WidgetProps) {
  const props = widget.props as { scenarios?: Record<string, Array<{ name: string; years: number[]; values: number[] }>> };
  const series: SyChartSeries[] = Object.entries(props.scenarios ?? {}).flatMap(([scenarioName, seriesList]) =>
    seriesList.map((s) => ({ name: `${s.name} — ${scenarioName}`, x: s.years, y: s.values, kind: 'line' as const })),
  );
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle="CO₂ (Mt)" />;
}

function ForecastWidget({ widget }: WidgetProps) {
  const props = widget.props as {
    hist_years: number[];
    hist_co2: Array<number | null>;
    holdout_years: number[];
    holdout_co2: Array<number | null>;
    forecast_years: number[];
    forecast_mean: number[];
    ci_upper: number[];
    ci_lower: number[];
  };
  const series: SyChartSeries[] = [
    { name: 'Historical', x: props.hist_years, y: props.hist_co2, kind: 'line' },
    { name: 'Holdout', x: props.holdout_years, y: props.holdout_co2, kind: 'line', dashed: true },
    { name: '95% CI', x: props.forecast_years, y: props.ci_upper, yLower: props.ci_lower, kind: 'band' },
    { name: 'Forecast', x: props.forecast_years, y: props.forecast_mean, kind: 'line' },
  ];
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle="CO₂ (Mt)" />;
}

function ForecastComparisonWidget({ widget }: WidgetProps) {
  const props = widget.props as {
    forecasts?: Array<{ country: string; hist_years: number[]; hist_co2: Array<number | null>; forecast_years: number[]; forecast_mean: number[] }>;
  };
  const series: SyChartSeries[] = (props.forecasts ?? []).map((f) => ({
    name: f.country,
    x: [...f.hist_years, ...f.forecast_years],
    y: [...f.hist_co2, ...f.forecast_mean],
    kind: 'line',
  }));
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle="CO₂ (Mt)" />;
}

function TopEmittersWidget({ widget }: WidgetProps) {
  const props = widget.props as { year?: number; emitters?: Array<{ country: string; iso_code: string; co2: number }> };
  const emitters = props.emitters ?? [];
  const name = `CO₂ Emissions${props.year ? `, ${props.year}` : ''}`;
  const series: SyChartSeries[] =
    widget.chart_kind === 'choropleth'
      ? [{ name, x: [], y: [], kind: 'choropleth', locations: emitters.map((e) => e.iso_code), colorValues: emitters.map((e) => e.co2), hoverUnit: 'MtCO₂' }]
      : [{ name, x: emitters.map((e) => e.country), y: emitters.map((e) => e.co2), kind: 'bar', colorValues: emitters.map((e) => e.co2) }];
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} yTitle={widget.chart_kind === 'choropleth' ? undefined : 'CO₂ (Mt)'} />;
}

function ModelComparisonWidget({ widget }: WidgetProps) {
  const props = widget.props as { columns?: string[]; rows?: Record<string, unknown>[] };
  const columns: ColDef<Record<string, unknown>>[] = (props.columns ?? []).map((c) => ({ field: c, headerName: humanize(c) }));
  return <GridWidget title={widget.title} columns={columns} rows={props.rows ?? []} />;
}

function GasCompositionWidget({ widget }: WidgetProps) {
  const props = widget.props as { decades?: number[]; series?: Array<{ gas_label: string; share: Array<number | null> }> };
  const decades = props.decades ?? [];
  const series = props.series ?? [];
  const rows = decades.map((decade, i) => {
    const row: Record<string, unknown> = { decade };
    for (const s of series) row[s.gas_label] = s.share[i];
    return row;
  });
  const columns: ColDef<Record<string, unknown>>[] = [
    { field: 'decade', headerName: 'Decade' },
    ...series.map((s) => ({ field: s.gas_label, headerName: s.gas_label })),
  ];
  return <GridWidget title={widget.title} columns={columns} rows={rows} />;
}

function ForecastSummaryWidget({ widget }: WidgetProps) {
  const props = widget.props as { rows?: Record<string, unknown>[] };
  const columns: ColDef<Record<string, unknown>>[] = [
    'country',
    'actual_2020',
    'forecast_2030',
    'forecast_2035',
    'forecast_2040',
    'pct_change_2020_2040',
  ].map((field) => ({ field, headerName: humanize(field) }));
  return <GridWidget title={widget.title} columns={columns} rows={props.rows ?? []} />;
}

function ScenarioCumulativeWidget({ widget }: WidgetProps) {
  const props = widget.props as {
    scenarios?: string[];
    rows?: Array<{ country: string; values: Record<string, number | null>; current_level: number | null }>;
  };
  const scenarios = props.scenarios ?? [];
  const rows = (props.rows ?? []).map((r) => {
    const row: Record<string, unknown> = { country: r.country, current_level: r.current_level };
    for (const s of scenarios) row[`cumulative_${s}`] = r.values[s];
    return row;
  });
  const columns: ColDef<Record<string, unknown>>[] = [
    { field: 'country', headerName: 'Country' },
    { field: 'current_level', headerName: 'Current Level' },
    ...scenarios.map((s) => ({ field: `cumulative_${s}`, headerName: `${s} Cumulative` })),
  ];
  return <GridWidget title={widget.title} columns={columns} rows={rows} />;
}

function CountryProfileCardWidget({ widget }: WidgetProps) {
  const props = widget.props as { co2: Array<number | null>; co2_per_capita: Array<number | null>; yoy_values: number[] };
  const latestCo2 = lastDefined(props.co2);
  const latestPerCapita = lastDefined(props.co2_per_capita);
  const latestYoy = lastDefined(props.yoy_values);
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <KpiStat label="CO₂ Emissions (Mt)" value={latestCo2 != null ? latestCo2.toLocaleString(undefined, { maximumFractionDigits: 1 }) : '—'} />
      <KpiStat label="CO₂ per Capita (t)" value={latestPerCapita != null ? latestPerCapita.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '—'} />
      {latestYoy != null && (
        <KpiStat
          label="Year-on-Year Change"
          value={`${latestYoy >= 0 ? '+' : ''}${latestYoy.toFixed(1)}%`}
          deltaDirection={latestYoy >= 0 ? 'bad' : 'good'}
        />
      )}
    </div>
  );
}

function CountryProfileChartWidget({ widget }: WidgetProps) {
  const props = widget.props as { years: number[]; co2: Array<number | null> };
  const series: SyChartSeries[] = [{ name: 'CO₂', x: props.years, y: props.co2, kind: 'line' }];
  return <ChartWidget title={widget.title} asOf={widget.as_of} series={series} xTitle="Year" yTitle="CO₂ (Mt)" />;
}

function MethodologyNotesWidget({ widget }: WidgetProps) {
  const props = widget.props as Record<string, string>;
  return (
    <Card header={<CardHeader title={widget.title} />}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {Object.entries(props).map(([key, text]) => (
          <div key={key}>
            <div className="__s9cmpx-label3" style={{ color: 'var(--__s9cmpx-static-text-weak)', marginBottom: 4 }}>
              {humanize(key)}
            </div>
            <div className="__s9cmpx-body3">{text}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// general_climate_node (graph.py) builds this widget directly, not via ui_selection.py's
// tool -> intent lookup -- its source_tool_call is the fixed literal "general_climate", not a
// real tool's cache key (no colon at all, so toolNameFromSourceTaggedCall returns it whole).
// Without this entry it would silently fall through to GenericFallbackWidget's "not recognized"
// message on every single general_climate-classified query, not just a genuinely unmapped tool.
function GeneralClimateWidget({ widget }: WidgetProps) {
  const props = widget.props as { text?: string };
  return (
    <Card header={<CardHeader title={widget.title} />}>
      <div className="__s9cmpx-body3">{props.text}</div>
    </Card>
  );
}

// Fallback for a widget shape not covered above -- an unmapped tool at this system boundary
// (arbitrary backend data) shouldn't crash the whole result section, but this repo's own "don't
// build for hypothetical futures" convention means every real tool gets its own render function
// above; this only ever fires if services/agent starts emitting a tool ui_selection.py doesn't
// know about, which would itself be a bug worth surfacing, not silently swallowing.
function GenericFallbackWidget({ widget }: WidgetProps) {
  if (widget.intent === 'grid') {
    const rows = Array.isArray(widget.props.rows) ? (widget.props.rows as Record<string, unknown>[]) : [];
    return <GridWidget title={widget.title} columns={genericColumns(rows)} rows={rows} />;
  }
  return (
    <Card header={<CardHeader title={widget.title} />}>
      <InlineAlert variant="warning">This result type isn&apos;t recognized yet.</InlineAlert>
    </Card>
  );
}

const RENDERERS: Record<string, (props: WidgetProps) => ReactElement> = {
  get_historical_emissions: HistoricalEmissionsWidget,
  get_scenario_projection: ScenarioProjectionWidget,
  compare_scenarios_across_countries: CompareScenariosWidget,
  get_forecast: ForecastWidget,
  get_forecast_comparison: ForecastComparisonWidget,
  get_top_emitters: TopEmittersWidget,
  get_model_comparison: ModelComparisonWidget,
  get_gas_composition_by_decade: GasCompositionWidget,
  get_forecast_summary: ForecastSummaryWidget,
  get_scenario_cumulative_impact: ScenarioCumulativeWidget,
  get_methodology_notes: MethodologyNotesWidget,
  general_climate: GeneralClimateWidget,
};

export function WidgetRenderer({ widget }: WidgetProps) {
  const toolName = toolNameFromSourceTaggedCall(widget.source_tool_call);
  // get_country_profile is the one tool that produces two different widgets from the same
  // source_tool_call (SPEC.md §8 ui_selection, "Corrections applied" advisory: distinguish by
  // widget.intent, not source_tool_call, since both widgets share the same source id).
  if (toolName === 'get_country_profile') {
    return widget.intent === 'chart' ? <CountryProfileChartWidget widget={widget} /> : <CountryProfileCardWidget widget={widget} />;
  }
  const Renderer = RENDERERS[toolName];
  return Renderer ? <Renderer widget={widget} /> : <GenericFallbackWidget widget={widget} />;
}
