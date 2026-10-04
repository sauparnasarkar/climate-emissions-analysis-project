import { InlineAlert } from 'design-system';
import { NOT_A_CLIMATE_MODEL } from '../lib/climateCopy';

// Route stub for the Temperature & GHG Correlation module (Area 2, Phase 2.4). The Overview and
// Landing link here from Step 3 on; the module's sections are built in later steps
// (ENHANCEMENTS.md "Section 2 plan", steps 7-9).
export default function ClimateCorrelationPage() {
  return (
    <div>
      <h1 className="__s9cmpx-headline2" style={{ margin: '0 0 8px' }}>Temperature &amp; GHG Correlation</h1>
      <p className="__s9cmpx-body3-short" style={{ maxWidth: 880, marginBottom: 16 }}>
        Emissions raise atmospheric CO₂, which traps heat and warms the planet. This module reads that chain from
        observations. It is descriptive: correlation is shown as context, not as proof of cause.
      </p>
      <InlineAlert variant="default">{`Sections are being added. ${NOT_A_CLIMATE_MODEL}`}</InlineAlert>
    </div>
  );
}
