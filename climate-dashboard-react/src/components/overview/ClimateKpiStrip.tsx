import type { ReactNode } from 'react';
import { NEGATIVE_COLOR, POSITIVE_COLOR } from '../../constants';
import { fmtAnomaly, type ClimateSignal, type YearValue } from '../../lib/climateSignal';
import { fmtInt, fmtPct } from '../../lib/landingData';
import { BaselineChip } from '../climate/BaselineChip';
import { BaselineInfo, type BaselineSpec } from '../climate/BaselineInfo';
import { SERIES_STYLES } from '../climate/seriesStyles';
import { Sparkline } from '../landing/Sparkline';

// The Overview's "global climate signal" KPI strip (Area 2, requirements §2.2 block 1, §2.5): emissions, change since the
// baseline (an index, 1990 = 100), atmospheric CO₂ and temperature anomaly. Every card carries its baseline as a chip and, behind
// the ⓘ, the full baseline detail (year, reference, formula, source range, excluded years). Every figure comes from the API.
// The climate cards are left out (never shown with zeros) when the climate data is missing; the two emissions cards stand alone.

export interface ClimateKpiEmissions {
  /** Latest year and the all-countries total for it, MtCO₂ */
  year: number;
  total: number;
  /** Percent change since the baseline year (the Overview's own figure) */
  pctChange: number;
  baselineYear: number;
  /** Annual world totals (MtCO₂), every year the globe series covers; includes the baseline year */
  series: YearValue[];
}

interface CardProps {
  tone: 'emissions' | 'concentration' | 'temperature';
  label: string;
  value: ReactNode;
  delta?: ReactNode;
  deltaColor?: string;
  spark?: ReactNode;
  sparkCaption?: string;
  chip: ReactNode;
  info: BaselineSpec;
}

function KpiCard({ tone, label, value, delta, deltaColor, spark, sparkCaption, chip, info }: CardProps) {
  return (
    <article className={`series--${tone} __s9cmpx-card __s9cmpx-card--with-border`} style={{ borderTop: '3px solid var(--series)', padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span className="__s9cmpx-label3" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>{label}</span>
        <BaselineInfo spec={info} label={label} />
      </div>
      <span className="__s9cmpx-headline4" style={{ lineHeight: 1.1, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      {delta && <span className="__s9cmpx-label2" style={{ color: deltaColor ?? 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>{delta}</span>}
      {spark && <div className="series-spark">{spark}</div>}
      {sparkCaption && <span className="__s9cmpx-body4" style={{ color: 'var(--area2-muted, var(--__s9cmpx-static-text-weak))' }}>{sparkCaption}</span>}
      <div>{chip}</div>
    </article>
  );
}

export function ClimateKpiStrip({ emissions, signal, mean5y }: { emissions: ClimateKpiEmissions; signal: ClimateSignal | null; mean5y: { value: number; year: number } | null }) {
  const { year, total, pctChange, baselineYear, series } = emissions;
  const first = series[0]?.year;
  const baselineTotal = series.find((p) => p.year === baselineYear)?.value;
  const indexSeries = baselineTotal ? series.filter((p) => p.year >= baselineYear).map((p) => ({ year: p.year, value: (p.value / baselineTotal) * 100 })) : [];
  const owidRange = first != null ? `OWID, ${first}–${year}` : `OWID, to ${year}`;
  const changeColor = pctChange >= 0 ? NEGATIVE_COLOR : POSITIVE_COLOR; // more emissions is the bad direction, as elsewhere on this page

  const emissionsInfo: BaselineSpec = {
    baseline: `${baselineYear} = 100`, reference: `World total in ${baselineYear}`, formula: `value ÷ value${baselineYear} × 100`,
    sourceRange: owidRange, excludedYears: 'None', note: `Kept at ${baselineYear} to match the ML training window used across the platform.`,
  };

  return (
    <div className="overview-kpi-strip" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
      <style>{SERIES_STYLES}</style>
      <KpiCard
        tone="emissions" label={`CO₂ emissions · ${year}`}
        value={<>{fmtInt(total)} <span className="__s9cmpx-body3">MtCO₂</span></>} delta="all countries"
        spark={<Sparkline values={series} />} sparkCaption={first != null ? `${first}–${year}` : undefined}
        chip={<BaselineChip baseline={String(baselineYear)} source="OWID" />} info={emissionsInfo}
      />
      <KpiCard
        tone="emissions" label="Change since baseline"
        value={<>{(100 + pctChange).toFixed(1)}</>} delta={`${fmtPct(pctChange)} · ${baselineYear} = 100`} deltaColor={changeColor}
        spark={indexSeries.length > 1 ? <Sparkline values={indexSeries} /> : undefined} sparkCaption={indexSeries.length > 1 ? `Index, ${baselineYear}–${year}` : undefined}
        chip={<BaselineChip baseline={`${baselineYear} = 100`} source="OWID" />} info={emissionsInfo}
      />
      {signal && (
        <>
          <KpiCard
            tone="concentration" label={`Atmospheric CO₂ · ${signal.concentration.year}`}
            value={<>{signal.concentration.value.toFixed(1)} <span className="__s9cmpx-body3">ppm</span></>}
            delta={signal.ppm1850 ? `${fmtPct((signal.concentration.value / signal.ppm1850 - 1) * 100)} vs pre-industrial (1850)` : undefined}
            spark={<Sparkline values={signal.series.concentration} markerYear={signal.spliceYear} />}
            sparkCaption={signal.spliceYear != null ? `Ice core to ${signal.spliceYear - 1} · Mauna Loa from ${signal.spliceYear}` : undefined}
            chip={<BaselineChip baseline="1850" source="NOAA + Law Dome" />}
            info={{
              baseline: '1850 (pre-industrial)', reference: 'Annual mean CO₂ in 1850 (Law Dome ice core)', formula: '(ppm ÷ ppm₁₈₅₀ − 1) × 100%',
              sourceRange: `NOAA GML + Law Dome, ${signal.series.concentration[0]?.year ?? '…'}–${signal.concentration.year}`, excludedYears: 'None',
              note: signal.spliceYear != null ? `Direct measurements start in ${signal.spliceYear}; earlier values are from the ice core.` : undefined,
            }}
          />
          <KpiCard
            tone="temperature" label={`Temperature anomaly · ${signal.temperature.year}`}
            value={fmtAnomaly(signal.temperature.value)} delta={mean5y ? `5-year mean ${mean5y.value.toFixed(2)} °C` : undefined}
            spark={<Sparkline values={signal.series.temperature} />} sparkCaption={`${signal.series.temperature[0]?.year ?? ''}–${signal.temperature.year}`}
            chip={<BaselineChip baseline="1850–1900" source="Berkeley Earth" />}
            info={{
              baseline: '1850–1900 average', reference: 'Mean anomaly 1850–1900, computed from the dataset itself', formula: 'ΔT = T − mean(T₁₈₅₀–₁₉₀₀)',
              sourceRange: `Berkeley Earth, ${signal.series.temperature[0]?.year ?? '…'}–${signal.temperature.year}`, excludedYears: 'None',
              note: signal.vintageCaveat ?? undefined,
            }}
          />
        </>
      )}
    </div>
  );
}
