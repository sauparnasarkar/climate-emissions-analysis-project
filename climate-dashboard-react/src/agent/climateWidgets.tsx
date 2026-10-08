import type { ComponentProps, ReactElement } from 'react';
import { useMemo } from 'react';
import { Card, CardHeader, ChartCard, DataTable, InlineAlert, KpiStat, Spinner, SyChart } from 'design-system';
import { api } from '../api/client';
import type {
  CorrelationCountryShareResponse,
  CorrelationEmissionsTemperatureResponse,
  CorrelationGhgCompositionResponse,
  CorrelationScenarioTemperatureResponse,
  CorrelationSeriesResponse,
} from '../api/correlationTypes';
import { AllGasRelationship } from '../components/module/AllGasRelationship';
import { GasComposition } from '../components/module/GasComposition';
import { HeadlineRelationship } from '../components/module/HeadlineRelationship';
import { ScenarioSection } from '../components/module/ScenarioSection';
import { useAsync } from '../hooks/useAsync';
import { useClimateSignal } from '../hooks/useClimateSignal';
import { buildAllGas } from '../lib/allGas';
import { buildClimateSignal } from '../lib/climateSignal';
import { buildComposition } from '../lib/gasComposition';
import { buildHeadline } from '../lib/headline';
import { buildScenarioView } from '../lib/scenarioView';
import { singleYearRows, sourceRows } from './climateRows';
import type { WidgetSpec } from './types';

// The Area 2 tools' widgets (ENHANCEMENTS.md decision 105; services/agent SPEC.md §15.2). Where the Correlation module already has a component for the
// same result, that component is used, fed the tool's own result through the module's own pure builders -- so an answer and the module page can
// never disagree, and nothing is typed in here. Everything the module component needs beyond the tool result (the observed temperature history, the
// concentration, the fossil-only comparison) is fetched from the same dashboard API the module page uses.

type SyChartSeries = ComponentProps<typeof SyChart>['series'][number];
interface WidgetProps {
  widget: WidgetSpec;
}

const asResult = <T,>(widget: WidgetSpec): T => widget.props as unknown as T;

function Unavailable({ children }: { children: string }) {
  return <InlineAlert variant="warning">{children}</InlineAlert>;
}

// --- emissions vs temperature -----------------------------------------------------------------------------------

/** A plain pairs chart (cumulative emissions against temperature) for a result the module has no component for -- the fossil-only variant, a
 * 1970 or 1990 window of the OWID series, or any case where the module's extra data could not be loaded. The fit, when one is published, is stated
 * in the caption; the chart is never titled or captioned as the headline relationship (the title comes from the agent, built from the result). */
function PairsChart({ widget, pair }: { widget: WidgetSpec; pair: CorrelationEmissionsTemperatureResponse }) {
  const fit = pair.fit as { slope?: number; ci95_hac?: number[]; r_squared?: number | null; unit?: string } | null;
  const points = pair.points ?? [];
  const series: SyChartSeries[] = [{ name: 'Years', x: points.map((p) => p.cumulative_emissions / 1000), y: points.map((p) => p.temperature), kind: 'marker' }];
  return (
    <ChartCard title={widget.title}>
      <SyChart series={series} xTitle={`${pair.x?.name ?? 'Cumulative emissions'} (Gt)`} yTitle={`${pair.y?.name ?? 'Temperature anomaly'} (°C)`} showLegend={false} />
      <p className="__s9cmpx-body4" style={{ margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' }}>
        {fit && typeof fit.slope === 'number'
          ? `Fitted slope ${fit.slope.toFixed(3)} ${fit.unit ?? ''}${Array.isArray(fit.ci95_hac) ? ` (95% interval ${fit.ci95_hac.map((v) => v.toFixed(3)).join('–')})` : ''}. A long-run relationship in observed data, not a climate model.`
          : 'No fit is published for this window; the pairs are shown as context only.'}
      </p>
    </ChartCard>
  );
}

function HeadlineWidget({ widget, pair }: { widget: WidgetSpec; pair: CorrelationEmissionsTemperatureResponse }) {
  const temperature = useAsync(() => api.correlationTemperature({ baseline: '1850_1900' }), []);
  const concentration = useAsync(() => api.correlationConcentration(), []);
  const fossil = useAsync(() => api.correlationEmissionsTemperature({ variant: 'fossil' }), []);
  const signal = useMemo(
    () => (temperature.data && concentration.data ? buildClimateSignal(pair, temperature.data, concentration.data) : null),
    [pair, temperature.data, concentration.data],
  );
  const headline = useMemo(() => (signal ? buildHeadline(signal, fossil.data) : null), [signal, fossil.data]);
  if (temperature.loading || concentration.loading) return <Spinner />;
  // The module's component needs the temperature and the concentration beside the pair; without them show the pair itself rather than nothing.
  if (!signal || !headline) return <PairsChart widget={widget} pair={pair} />;
  return <HeadlineRelationship signal={signal} headline={headline} embedded />;
}

export function EmissionsTemperatureWidget({ widget }: WidgetProps): ReactElement {
  const pair = asResult<CorrelationEmissionsTemperatureResponse>(widget);
  // Decided from the API's own fields (source, baseline, variant), never from a label: only the pre-industrial total OWID fit is the headline.
  if (pair.source === 'primap_ghg' && pair.baseline === '1970') {
    const allGas = buildAllGas(pair);
    if (allGas) return <AllGasRelationship allGas={allGas} embedded />;
  }
  if (pair.source === 'owid_co2' && pair.baseline === 'preindustrial' && pair.variant !== 'fossil') return <HeadlineWidget widget={widget} pair={pair} />;
  return <PairsChart widget={widget} pair={pair} />;
}

// --- greenhouse-gas mix ------------------------------------------------------------------------------------------

export function GhgCompositionWidget({ widget }: WidgetProps): ReactElement {
  const result = asResult<CorrelationGhgCompositionResponse>(widget);
  const composition = useMemo(() => buildComposition(result), [result]);
  if (widget.intent === 'grid' || (result.years?.length ?? 0) === 1) {
    const rows = singleYearRows(result);
    return (
      <Card header={<CardHeader title={widget.title} />}>
        <DataTable columns={[{ field: 'gas', headerName: 'Gas' }, { field: 'mtco2e', headerName: 'MtCO₂e' }, { field: 'share', headerName: 'Share' }]} rows={rows} />
      </Card>
    );
  }
  if (!composition) return <Unavailable>The greenhouse-gas mix could not be drawn from this result.</Unavailable>;
  return <GasComposition composition={composition} embedded />;
}

// --- scenario temperatures ---------------------------------------------------------------------------------------

export function ScenarioTemperatureWidget({ widget }: WidgetProps): ReactElement {
  const result = asResult<CorrelationScenarioTemperatureResponse>(widget);
  const climate = useClimateSignal();
  const fossil = useAsync(() => api.correlationEmissionsTemperature({ variant: 'fossil' }), []);
  const view = useMemo(
    () => buildScenarioView(result, fossil.data, climate.temperatureSeries, climate.mean5ySeries),
    [result, fossil.data, climate.temperatureSeries, climate.mean5ySeries],
  );
  if (!climate.settled || fossil.loading) return <Spinner />;
  if (!view) return <Unavailable>The scenario temperatures could not be drawn from this result.</Unavailable>;
  // The agent flags a lead that already carries the pipeline's reading note (services/agent SPEC §15.11); the section's own "Reading note" panel
  // would then repeat the same paragraph directly beneath it, so it is left out. When the lead was composed across tools it keeps its panel.
  const leadHasNote = (widget.summary as { lead_includes_reading_note?: boolean } | null | undefined)?.lead_includes_reading_note === true;
  return <ScenarioSection view={leadHasNote ? { ...view, readingNote: null } : view} embedded />;
}

// --- country shares -----------------------------------------------------------------------------------------------

/** `/country-share` answers a year outside its coverage (or a country with no rows) with HTTP 200 and nothing to draw, plus a note: say so, naming the
 * year and the coverage, instead of an empty chart -- the same wording the module's country view uses. */
function NoShares({ result }: { result: CorrelationCountryShareResponse }) {
  const [lo, hi] = result.coverage ?? [];
  return <Unavailable>{`No country shares are available${result.year != null ? ` for ${result.year}` : ''}.${lo != null && hi != null ? ` Coverage is ${lo}–${hi}.` : ''}`}</Unavailable>;
}

export function CountryShareWidget({ widget }: WidgetProps): ReactElement {
  const result = asResult<CorrelationCountryShareResponse>(widget);
  const nothing = result.mode === 'series' ? !(result.series ?? []).some((s) => s.points.length > 0) : (result.rows ?? []).length === 0;
  if (nothing) return <NoShares result={result} />;
  if (result.mode === 'series') {
    const series: SyChartSeries[] = (result.series ?? []).map((s) => ({ name: s.name, x: s.points.map((p) => p.year), y: s.points.map((p) => p.share_pct), kind: 'line' as const }));
    return (
      <ChartCard title={widget.title}>
        <SyChart series={series} xTitle="Year" yTitle="Cumulative share of emissions (%)" />
      </ChartCard>
    );
  }
  const rows = result.rows ?? [];
  const series: SyChartSeries[] = [{ name: 'Cumulative share', x: rows.map((r) => r.name), y: rows.map((r) => r.share_pct), kind: 'bar' }];
  return (
    <ChartCard title={widget.title}>
      <SyChart series={series} xTitle="Country" yTitle="Cumulative share of emissions (%)" showLegend={false} />
    </ChartCard>
  );
}

// --- concentration and temperature -----------------------------------------------------------------------------

export function IndicatorWidget({ widget }: WidgetProps): ReactElement {
  const result = asResult<CorrelationSeriesResponse>(widget);
  const summary = (widget.summary ?? {}) as { last_value?: number; last_year?: number; reference?: string };
  const isConcentration = widget.source_tool_call.startsWith('get_co2_concentration');
  const unit = isConcentration ? 'ppm' : '°C';
  if (widget.intent === 'card') {
    const v = summary.last_value;
    return (
      <Card header={<CardHeader title={widget.title} />}>
        <KpiStat label={`${isConcentration ? 'CO₂ concentration' : 'Temperature anomaly'}${summary.last_year ? ` · ${summary.last_year}` : ''}`} value={v == null ? '—' : `${v.toLocaleString(undefined, { maximumFractionDigits: isConcentration ? 1 : 2 })} ${unit}`} />
      </Card>
    );
  }
  const pts = (result.points ?? []).filter((p) => p.value != null);
  const series: SyChartSeries[] = [{ name: isConcentration ? 'CO₂ concentration' : 'Temperature anomaly', x: pts.map((p) => p.year), y: pts.map((p) => p.value as number), kind: 'line' }];
  return (
    <ChartCard title={widget.title}>
      <SyChart series={series} xTitle="Year" yTitle={isConcentration ? 'CO₂ concentration (ppm)' : 'Temperature anomaly (°C)'} showLegend={false} />
    </ChartCard>
  );
}

// --- sources and methodology ---------------------------------------------------------------------------------------

export function CorrelationMetadataWidget({ widget }: WidgetProps): ReactElement {
  const summary = (widget.summary ?? {}) as { sources?: Array<{ id: string; coverage?: number[] | null; retrieved_at?: string | null; license?: string | null }>; stale_outputs?: string[] };
  const rows = sourceRows(summary.sources ?? []);
  return (
    <Card header={<CardHeader title={widget.title} />}>
      {(summary.stale_outputs?.length ?? 0) > 0 && <InlineAlert variant="warning">{`Some climate outputs are missing or out of date: ${summary.stale_outputs!.join(', ')}.`}</InlineAlert>}
      <DataTable columns={[{ field: 'source', headerName: 'Source' }, { field: 'coverage', headerName: 'Coverage' }, { field: 'retrieved', headerName: 'Retrieved' }, { field: 'licence', headerName: 'Licence' }]} rows={rows} />
    </Card>
  );
}
