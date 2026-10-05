import { useMemo, useState } from 'react';
import { InlineAlert, JumpLinks, Spinner, useReducedMotion } from 'design-system';
import type { JumpLinkItem } from 'design-system/components/JumpLinks/JumpLinks';
import { api } from '../api/client';
import { CausalChain } from '../components/module/CausalChain';
import { AllGasRelationship } from '../components/module/AllGasRelationship';
import { HeadlineRelationship } from '../components/module/HeadlineRelationship';
import { useAsync } from '../hooks/useAsync';
import { useClimateSignal } from '../hooks/useClimateSignal';
import { useElementHeight } from '../hooks/useElementHeight';
import { useJumpToHashOnLoad } from '../hooks/useJumpToHashOnLoad';
import { CAUSAL_CHAIN_ANCHOR, GLOBAL_RELATIONSHIP_ANCHOR, NOT_A_CLIMATE_MODEL } from '../lib/climateCopy';
import { buildAllGas } from '../lib/allGas';
import { buildHeadline } from '../lib/headline';
import { latestWorldTotal } from '../lib/mapSeries';
import { CLIMATE_SERIES_START_YEAR } from '../constants';

const STICKY_HEADER_PX = 68;
const JUMP_ROW_PX = 52;
const JUMP_ROW_GAP_PX = 10;

const CHAIN_JUMP: JumpLinkItem = { id: CAUSAL_CHAIN_ANCHOR, label: 'Causal chain', href: `#${CAUSAL_CHAIN_ANCHOR}` };
const RELATIONSHIP_JUMP: JumpLinkItem = { id: GLOBAL_RELATIONSHIP_ANCHOR, label: 'Global relationship', href: `#${GLOBAL_RELATIONSHIP_ANCHOR}` };

/**
 * The Temperature & GHG Correlation module (Area 2, Phases 2.4 and 2.5; ENHANCEMENTS.md decision 65). 7a: the causal chain and the headline
 * relationship. Descriptive throughout: correlation as context, never proof of cause. If the climate data is unavailable the module says so once and
 * shows no chain or relationship -- never zeros.
 */
export default function ClimateCorrelationPage() {
  const climate = useClimateSignal();
  const fossil = useAsync(async () => api.correlationEmissionsTemperature({ variant: 'fossil' }), []);
  const allGasQuery = useAsync(async () => api.correlationEmissionsTemperature({ source: 'primap_ghg' }), []);
  const world = useAsync(async () => api.worldMapSeries(CLIMATE_SERIES_START_YEAR), []);
  const reduceMotion = useReducedMotion();
  const [stickyRow, setStickyRow] = useState<HTMLElement | null>(null);
  const stickyHeight = useElementHeight(stickyRow);
  const jumpRowPx = stickyHeight ? Math.ceil(stickyHeight) + JUMP_ROW_GAP_PX : JUMP_ROW_PX;

  const signal = climate.signal;
  // The latest year that has data: an all-null final row is missing, not a world total of zero.
  const emissions = useMemo(() => (world.data ? latestWorldTotal(world.data) : null), [world.data]);
  const allGas = useMemo(() => buildAllGas(allGasQuery.data), [allGasQuery.data]);
  const headline = useMemo(() => (signal ? buildHeadline(signal, fossil.data) : null), [signal, fossil.data]);

  // A deep link waits for the climate request and the first measurement of the anchor row (its height depends on whether it wrapped).
  useJumpToHashOnLoad(climate.done && stickyHeight !== null, reduceMotion);

  return (
    <div className="climate-module">
      <style>{`.climate-module [id] { scroll-margin-top: ${STICKY_HEADER_PX + jumpRowPx}px; }`}</style>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Temperature &amp; GHG Correlation</h1>
      <p className="__s9cmpx-body3-short" style={{ maxWidth: 880, marginBottom: 16 }}>
        Emissions raise atmospheric CO₂, which traps heat and warms the planet. This module reads that chain from
        observations. It is descriptive: correlation is shown as context, not as proof of cause.
      </p>
      {!climate.settled ? (
        <Spinner />
      ) : !signal || !headline ? (
        <InlineAlert variant="warning">{`The climate data is unavailable right now, so the chain and the relationship are not shown. ${NOT_A_CLIMATE_MODEL}`}</InlineAlert>
      ) : (
        <>
          <div ref={setStickyRow} style={{ marginBottom: 16, position: 'sticky', top: STICKY_HEADER_PX, zIndex: 5, background: 'var(--__s9cmpx-static-background-weak)', padding: '4px 0' }}>
            <JumpLinks items={[CHAIN_JUMP, RELATIONSHIP_JUMP]} />
          </div>
          <CausalChain signal={signal} emissions={emissions} />
          <HeadlineRelationship signal={signal} headline={headline} hasAllGas={allGas !== null} />
          {allGas && <AllGasRelationship allGas={allGas} />}
        </>
      )}
    </div>
  );
}
