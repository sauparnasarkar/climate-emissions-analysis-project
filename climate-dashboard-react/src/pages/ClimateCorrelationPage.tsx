import { useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { InlineAlert, JumpLinks, Spinner, useReducedMotion } from 'design-system';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { CausalChain } from '../components/module/CausalChain';
import { CountryView } from '../components/module/CountryView';
import { GasComposition } from '../components/module/GasComposition';
import { DerivationAccordion } from '../components/module/DerivationAccordion';
import { MethodologySection } from '../components/module/MethodologySection';
import { ScenarioSection } from '../components/module/ScenarioSection';
import { AllGasRelationship } from '../components/module/AllGasRelationship';
import { HeadlineRelationship } from '../components/module/HeadlineRelationship';
import { useAsync } from '../hooks/useAsync';
import { useClimateSignal } from '../hooks/useClimateSignal';
import { useElementHeight } from '../hooks/useElementHeight';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import { CAUSAL_CHAIN_ANCHOR, GLOBAL_RELATIONSHIP_ANCHOR, NOT_A_CLIMATE_MODEL } from '../lib/climateCopy';
import { buildAllGas } from '../lib/allGas';
import { COUNTRY_VIEW_ANCHOR } from '../lib/countryView';
import { ALL_GAS_ANCHOR } from '../lib/allGas';
import { GAS_COMPOSITION_ANCHOR } from '../lib/gasComposition';
import { buildComposition } from '../lib/gasComposition';
import { buildDerivation } from '../lib/derivation';
import { buildHeadline } from '../lib/headline';
import { METHODOLOGY_ANCHOR } from '../lib/methodology';
import { SCENARIOS_ANCHOR, buildScenarioView } from '../lib/scenarioView';
import { latestWorldTotal } from '../lib/mapSeries';
import { CLIMATE_SERIES_START_YEAR } from '../constants';

const STICKY_HEADER_PX = 68;
const JUMP_ROW_PX = 52;
const JUMP_ROW_GAP_PX = 10;

const CHAIN_JUMP: JumpLinkItem = { id: CAUSAL_CHAIN_ANCHOR, label: 'Causal chain', href: `#${CAUSAL_CHAIN_ANCHOR}` };
const RELATIONSHIP_JUMP: JumpLinkItem = { id: GLOBAL_RELATIONSHIP_ANCHOR, label: 'Global relationship', href: `#${GLOBAL_RELATIONSHIP_ANCHOR}` };
const METHODOLOGY_JUMP: JumpLinkItem = { id: METHODOLOGY_ANCHOR, label: 'Methodology', href: `#${METHODOLOGY_ANCHOR}` };
const SCENARIOS_JUMP: JumpLinkItem = { id: SCENARIOS_ANCHOR, label: 'Scenarios', href: `#${SCENARIOS_ANCHOR}` };
const COUNTRY_JUMP: JumpLinkItem = { id: COUNTRY_VIEW_ANCHOR, label: 'Country view', href: `#${COUNTRY_VIEW_ANCHOR}` };

/**
 * The Temperature & GHG Correlation module (Area 2, Phases 2.4 and 2.5; ENHANCEMENTS.md decision 65). 7a: the causal chain and the headline
 * relationship. Descriptive throughout: correlation as context, never proof of cause. If the climate data is unavailable the module says so once and
 * shows no chain or relationship -- never zeros.
 */
export default function ClimateCorrelationPage() {
  const climate = useClimateSignal();
  const fossil = useAsync(async () => api.correlationEmissionsTemperature({ variant: 'fossil' }), []);
  const allGasQuery = useAsync(async () => api.correlationEmissionsTemperature({ source: 'primap_ghg' }), []);
  const compositionQuery = useAsync(async () => api.correlationGhgComposition({ startYear: 1970 }), []);
  const metaQuery = useAsync(async () => api.correlationMeta(), []);
  const scenarioQuery = useAsync(async () => api.correlationScenarioTemperature(), []);
  const world = useAsync(async () => api.worldMapSeries(CLIMATE_SERIES_START_YEAR), []);
  const reduceMotion = useReducedMotion();
  const [stickyRow, setStickyRow] = useState<HTMLElement | null>(null);
  const stickyHeight = useElementHeight(stickyRow);
  const jumpRowPx = stickyHeight ? Math.ceil(stickyHeight) + JUMP_ROW_GAP_PX : JUMP_ROW_PX;

  const signal = climate.signal;
  // The latest year that has data: an all-null final row is missing, not a world total of zero.
  const emissions = useMemo(() => (world.data ? latestWorldTotal(world.data) : null), [world.data]);
  const allGas = useMemo(() => buildAllGas(allGasQuery.data), [allGasQuery.data]);
  const composition = useMemo(() => buildComposition(compositionQuery.data), [compositionQuery.data]);
  // The scenario output with the observed history it continues from: the fossil pair (the pathways' own basis) and the temperature series.
  const scenarios = useMemo(
    () => buildScenarioView(scenarioQuery.data, fossil.data, climate.temperatureSeries, climate.mean5ySeries),
    [scenarioQuery.data, fossil.data, climate.temperatureSeries, climate.mean5ySeries],
  );
  const derivation = useMemo(() => buildDerivation(climate.headline), [climate.headline]);
  const headline = useMemo(() => (signal ? buildHeadline(signal, fossil.data) : null), [signal, fossil.data]);

  // A deep link waits for the first measurement of the anchor row (its height depends on whether it wrapped) and for the request behind its target:
  // the climate signal for the chain and relationship, the all-gas or composition request for those sections (the country view is always there).
  const { hash } = useLocation();
  const targetReady =
    hash === `#${ALL_GAS_ANCHOR}` ? !allGasQuery.loading
    : hash === `#${GAS_COMPOSITION_ANCHOR}` ? !compositionQuery.loading
    : hash === `#${COUNTRY_VIEW_ANCHOR}` ? true
    : hash === `#${SCENARIOS_ANCHOR}` ? !scenarioQuery.loading
    : hash === `#${METHODOLOGY_ANCHOR}` ? !metaQuery.loading && climate.done
    : climate.done;
  useJumpToHashOnLoad(targetReady && stickyHeight !== null, reduceMotion);
  const jumpItems = [...(signal ? [CHAIN_JUMP, RELATIONSHIP_JUMP] : []), COUNTRY_JUMP, ...(scenarios ? [SCENARIOS_JUMP] : []), METHODOLOGY_JUMP];

  return (
    <div className="climate-module">
      <style>{`.climate-module [id] { scroll-margin-top: ${STICKY_HEADER_PX + jumpRowPx}px; }`}</style>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Temperature &amp; GHG Correlation</h1>
      <p className="__s9cmpx-body3-short" style={{ maxWidth: 880, marginBottom: 16 }}>
        Emissions raise atmospheric CO₂, which traps heat and warms the planet. This module reads that chain from
        observations. It is descriptive: correlation is shown as context, not as proof of cause.
      </p>
      <div ref={setStickyRow} style={{ marginBottom: 16, position: 'sticky', top: STICKY_HEADER_PX, zIndex: 5, background: 'var(--__s9cmpx-static-background-weak)', padding: '4px 0' }}>
        <JumpLinks items={jumpItems} />
      </div>
      {!climate.settled ? (
        <Spinner />
      ) : !signal || !headline ? (
        <InlineAlert variant="warning">{`The climate data is unavailable right now, so the chain and the relationship are not shown. ${NOT_A_CLIMATE_MODEL}`}</InlineAlert>
      ) : (
        <>
          <CausalChain signal={signal} emissions={emissions} />
          <HeadlineRelationship signal={signal} headline={headline} hasAllGas={allGas !== null} />
        </>
      )}
      {/* The sections below load on their own requests: one failing leaves the others standing. Without the headline they sit under a heading of their own. */}
      {!headline && (allGas || composition) && <h2 className="__s9cmpx-headline5" style={{ margin: '0 0 12px' }}>Global relationship</h2>}
      {allGas && <AllGasRelationship allGas={allGas} />}
      {composition && <GasComposition composition={composition} />}
      <CountryView temperature={climate.temperatureSeries} mean5y={climate.mean5ySeries.length ? climate.mean5ySeries : null} />
      {scenarios && <ScenarioSection view={scenarios} />}
      <MethodologySection meta={metaQuery.data} metaFailed={metaQuery.error !== null} splice={climate.splice}>
        {derivation && <DerivationAccordion derivation={derivation} />}
      </MethodologySection>
    </div>
  );
}
