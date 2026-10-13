import type { ComponentProps, ReactElement } from 'react';
import { useMemo, useRef } from 'react';
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
import { useCategoricalPalette } from '../hooks/useCategoricalPalette';
import { useClimateSignal } from '../hooks/useClimateSignal';
import { buildAllGas } from '../lib/allGas';
import { buildClimateSignal } from '../lib/climateSignal';
import { buildComposition } from '../lib/gasComposition';
import { buildHeadline } from '../lib/headline';
import { fmtGt } from '../lib/cumulative';
import { cumulativeAreaSeries } from '../lib/historicalCumulative';
import { buildScenarioView } from '../lib/scenarioView';
import { shareToCumulative, shareVsAnnualLines, sinceEmittedLines, sinceRebase, SINGLE_LINE_COLOR } from '../lib/shareViews';
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
  return <Unavailable>{`No country shares are available${result.year != null ? ` for ${result.year}` : ''}.${lo != null && hi != null ? ` Coverage is ${lo}–${hi}.` : ''}${result.notes.length ? ` ${result.notes.join(' ')}` : ''}`}</Unavailable>;
}

/** What a share result's amounts are, from its own source and gas scope (never assumed to be OWID CO₂): total greenhouse gases are CO₂-equivalent. */
function shareLabels(result: Pick<CorrelationCountryShareResponse, 'source' | 'gas_scope'>): { unit: string; gas: string; source: string; short: string; shareOf: string; totalOf: string } {
  const ghg = result.gas_scope === 'total_ghg';
  const primap = result.source === 'primap_hist';
  return {
    unit: ghg ? 'GtCO₂e' : 'GtCO₂',
    gas: ghg ? 'greenhouse gases (CO₂e)' : 'CO₂',
    source: primap ? `PRIMAP-hist ${ghg ? 'total greenhouse gases (CO₂e)' : 'CO₂'}` : 'Fossil and cement CO₂ · OWID',
    short: primap ? 'PRIMAP-hist' : 'Fossil and cement',
    // what a share is OF: the World's emissions for OWID; PRIMAP-hist has no world aggregate, so its own total (the summary's `since.basis` says the same)
    shareOf: primap ? "PRIMAP-hist's own total" : "the world's emissions",
    // the cumulative share's denominator: the World total for OWID, PRIMAP-hist's own total (it has no world aggregate)
    totalOf: primap ? "PRIMAP-hist's own total" : 'world total',
  };
}

interface SinceSummary {
  year: number;
  period: string;
  rank_of?: number;
  countries?: Array<{ name: string; emitted_gt?: number | null; share_of_period_pct?: number | null; rank?: number | null }>;
}

interface ShareSummaryCountry {
  last_year?: number | null;
  last_share_pct?: number | null;
  first_year?: number | null;
  first_share_pct?: number | null;
  last_cumulative_gt?: number | null;
  rank?: number | null;
  rank_of?: number | null;
}

/** A single country's three figures (cumulative total, share of the World total, rank), from the tool's own summary: the same trio Country Profile shows. */
function ShareFigures({ widget, result }: WidgetProps & { result: CorrelationCountryShareResponse }): ReactElement | null {
  const L = shareLabels(result);
  const summary = (widget.summary ?? {}) as { mode?: string; countries?: ShareSummaryCountry[]; since?: SinceSummary };
  const c = summary.mode === 'series' && summary.countries?.length === 1 ? summary.countries[0] : null;
  const pct = (v: number | null | undefined) => (v == null ? '—' : `${v.toFixed(1)}%`);
  const since = summary.since;
  const sc = since?.countries?.length === 1 ? since.countries[0] : null;
  if (since && sc && sc.emitted_gt != null) {
    // Emissions in a period: its own three figures, labelled with the period, never "since records began" (that is the other quantity).
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: 16, margin: '0 0 12px' }}>
        <KpiStat card label={`Emitted ${since.period}`} value={`${fmtGt(sc.emitted_gt)} ${L.unit}`} delta={L.short} deltaDirection="neutral" />
        <KpiStat card label={`Share of ${L.shareOf} ${since.period}`} value={pct(sc.share_of_period_pct)} deltaDirection="neutral" />
        {sc.rank != null && since.rank_of != null && <KpiStat card label={`Rank by emissions ${since.period}`} value={`#${sc.rank}`} delta={`of ${since.rank_of} countries`} deltaDirection="neutral" />}
      </div>
    );
  }
  if (!c || c.last_cumulative_gt == null || c.last_share_pct == null) return null;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: 16, margin: '0 0 12px' }}>
      <KpiStat card label={`Cumulative ${L.gas} since records began · ${c.last_year ?? ''}`} value={`${fmtGt(c.last_cumulative_gt)} ${L.unit}`} delta={L.short} deltaDirection="neutral" />
      <KpiStat card label={`Share of ${L.totalOf}`} value={pct(c.last_share_pct)} delta={c.first_share_pct == null || c.first_share_pct < 0.05 ? undefined : `${pct(c.first_share_pct)} in ${c.first_year}`} deltaDirection="neutral" />
      {c.rank != null && c.rank_of != null && <KpiStat card label={`Rank by cumulative ${L.gas} · ${c.last_year ?? ''}`} value={`#${c.rank}`} delta={`of ${c.rank_of} countries`} deltaDirection="neutral" />}
    </div>
  );
}

const caption = { margin: '8px 0 0', color: 'var(--__s9cmpx-static-text-weak)' } as const;

/** Stacked area of cumulative CO₂ in Gt with a Rest of world band: the Historical Trends Cumulative view, on the tool's own result (OWID only). */
function ShareAreaView({ widget, result }: { widget: WidgetSpec; result: CorrelationCountryShareResponse }): ReactElement | null {
  const rootRef = useRef<HTMLDivElement>(null);
  const palette = useCategoricalPalette(rootRef);
  const rebase = useMemo(() => sinceRebase(widget.summary), [widget.summary]);
  const data = useMemo(() => shareToCumulative(result, rebase), [result, rebase]);
  if (!data) return null;
  const names = data.series.map((s) => s.name).join(', ');
  const period = (widget.summary as { since?: SinceSummary } | null | undefined)?.since?.period;
  return (
    <div ref={rootRef}>
      <ShareFigures widget={widget} result={result} />
      <ChartCard title={widget.title}>
        <SyChart
          height={320}
          xTitle="Year"
          yTitle="Cumulative CO₂ (GtCO₂)"
          ariaLabel={`Stacked area chart of ${period ? `CO₂ emitted ${period}` : 'cumulative CO₂'} in gigatonnes for ${names} and Rest of world, ${data.years[0]} to ${data.years[data.years.length - 1]}`}
          series={cumulativeAreaSeries(data, palette)}
        />
        <p className="__s9cmpx-body4" style={caption}>
          {period
            ? `Fossil and cement CO₂ · OWID · emissions in ${period}: each country's cumulative total in each year minus its total the year before ${data.years[0]}, so every area starts at zero. Rest of world = the World's emissions in the period minus the countries shown, so it includes international aviation and shipping.`
            : `Fossil and cement CO₂ · OWID · counted from each country's first record, shown from ${data.years[0]}. Rest of world = World total minus the countries shown, so it includes international aviation and shipping.`}
        </p>
      </ChartCard>
    </div>
  );
}

/** Emissions in a period as one line per country, in Gt from zero in the first year: the since-answer chart where there is no World total to stack against (PRIMAP-hist). */
function SinceLinesView({ widget, result }: { widget: WidgetSpec; result: CorrelationCountryShareResponse }): ReactElement | null {
  const rebase = useMemo(() => sinceRebase(widget.summary), [widget.summary]);
  const lines = useMemo(() => sinceEmittedLines(result, rebase), [result, rebase]);
  if (!lines) return null;
  const L = shareLabels(result);
  const period = (widget.summary as { since?: SinceSummary } | null | undefined)?.since?.period ?? '';
  const gasName = L.gas === 'CO₂' ? 'CO₂' : 'Greenhouse gases (CO₂e)';
  return (
    <>
      <ShareFigures widget={widget} result={result} />
      <ChartCard title={widget.title}>
        <SyChart
          height={320}
          xTitle="Year"
          yTitle={`${gasName} emitted ${period} (${L.unit})`}
          ariaLabel={`Line chart of ${L.gas} emitted ${period} in gigatonnes for ${lines.map((l) => l.name).join(', ')}, ${lines[0].years[0]} to ${lines[0].years[lines[0].years.length - 1]}`}
          series={lines.map((l) => ({ name: l.name, x: l.years, y: l.gt, kind: 'line' as const }))}
        />
        <p className="__s9cmpx-body4" style={caption}>
          {L.source} · emissions in {period}: each country&rsquo;s cumulative total in each year minus its total the year before {lines[0].years[0]}, so every line starts at zero. There is no World total in this source to show a Rest of world against.
        </p>
      </ChartCard>
    </>
  );
}

/** One country's share of everything emitted so far (solid) against its share of each year's emissions (dotted): Country Profile's comparison, on the tool's own result. */
function ShareVsAnnualView({ widget, result }: { widget: WidgetSpec; result: CorrelationCountryShareResponse }): ReactElement | null {
  const lines = useMemo(() => shareVsAnnualLines(result), [result]);
  if (!lines) return null;
  const L = shareLabels(result);
  return (
    <>
      <ShareFigures widget={widget} result={result} />
      <ChartCard title={widget.title}>
        <p className="__s9cmpx-body4" style={{ ...caption, margin: '0 0 8px' }}>
          Solid line: share of all {L.gas} emitted so far. Dotted line: share of each year&rsquo;s emissions. When the dotted line is above the solid one, the share of the total is still rising.
        </p>
        <SyChart
          height={280}
          xTitle="Year"
          yTitle={`% of ${L.totalOf}`}
          ariaLabel={`Line chart of ${lines.name}'s share of everything emitted so far and of each year's ${L.gas} emissions, as a percent of ${L.totalOf}, ${lines.years[0]} to ${lines.years[lines.years.length - 1]}`}
          series={[
            { name: 'Share of cumulative total', x: lines.years, y: lines.cumulative, kind: 'line', color: SINGLE_LINE_COLOR },
            { name: "Share of that year's emissions", x: lines.years, y: lines.annual, kind: 'line', color: SINGLE_LINE_COLOR, dashed: true },
          ]}
        />
      </ChartCard>
    </>
  );
}

/** A ranking by emissions in a period ("the top emitters since 1970"): bars in Gt, with the period in the axis title. */
function SinceRankingView({ widget, result }: { widget: WidgetSpec; result: CorrelationCountryShareResponse }): ReactElement {
  const rows = result.since_rows ?? [];
  const period = (widget.summary as { since?: SinceSummary } | null | undefined)?.since?.period ?? `${result.since_year}–${result.year}`;
  const L = shareLabels(result);
  const series: SyChartSeries[] = [{ name: `Emitted ${period}`, x: rows.map((r) => r.name), y: rows.map((r) => (r.emitted_gt ?? r.emitted_mt / 1000)), kind: 'bar' }];
  return (
    <ChartCard title={widget.title}>
      <SyChart series={series} xTitle="Country" yTitle={`${L.gas === 'CO₂' ? 'CO₂' : 'Greenhouse gases (CO₂e)'} emitted ${period} (${L.unit})`} showLegend={false} ariaLabel={`Bar chart of ${L.gas} emitted ${period} in gigatonnes for the ${rows.length} largest emitters`} />
      <p className="__s9cmpx-body4" style={caption}>
        {L.source} · emissions in {period}: each country&rsquo;s cumulative total at the end year minus its total the year before {result.since_year}. Shares of the period are of {L.shareOf} in it.
      </p>
    </ChartCard>
  );
}

export function CountryShareWidget({ widget }: WidgetProps): ReactElement {
  const result = asResult<CorrelationCountryShareResponse>(widget);
  if (result.mode !== 'series' && (result.since_rows ?? []).length > 0) return <SinceRankingView widget={widget} result={result} />;
  const nothing = result.mode === 'series' ? !(result.series ?? []).some((s) => s.points.length > 0) : (result.rows ?? []).length === 0;
  if (nothing) return <NoShares result={result} />;
  // A view that cannot be drawn honestly (no World total for a PRIMAP-hist share, no annual share, no points) falls through to the lines below.
  if (result.mode === 'series' && widget.view === 'cumulative_area' && shareToCumulative(result, sinceRebase(widget.summary))) return <ShareAreaView widget={widget} result={result} />;
  if (result.mode === 'series' && widget.view === 'emitted_lines' && sinceEmittedLines(result, sinceRebase(widget.summary))) return <SinceLinesView widget={widget} result={result} />;
  if (result.mode === 'series' && widget.view === 'share_vs_annual' && shareVsAnnualLines(result)) return <ShareVsAnnualView widget={widget} result={result} />;
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
