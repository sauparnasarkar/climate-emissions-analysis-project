import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { META } from '../../test/climateFixtures';
import { MethodologySection } from './MethodologySection';

const SPLICE = { year: 1959, overlapYears: [1959, 2004] as [number, number], gapPpm: -0.28, maxAbsOverlapGapPpm: 3.9 };

describe('MethodologySection', () => {
  it('has the section heading and says every figure is read from the pipeline output', () => {
    render(<MethodologySection meta={META} metaFailed={false} splice={SPLICE} />);
    expect(screen.getByRole('heading', { level: 2, name: 'Methodology & sources' })).toBeInTheDocument();
    expect(document.getElementById('methodology')).not.toBeNull();
    expect(screen.getByText(/Every figure on this page is read from the pipeline output/)).toBeInTheDocument();
  });

  it('shows a sources table with column headers and the API\'s coverage, vintage and licence for each source', () => {
    render(<MethodologySection meta={META} metaFailed={false} splice={SPLICE} />);
    const table = screen.getByRole('table', { name: 'Sources' });
    expect(within(table).getAllByRole('columnheader').map((c) => c.textContent)).toEqual(['Source', 'Used for', 'Coverage', 'Vintage', 'Licence']);
    const berkeley = within(table).getByRole('row', { name: /Berkeley Earth/ });
    expect(berkeley).toHaveTextContent('1850–2024');
    expect(berkeley).toHaveTextContent('file of 2025-01-10');
    expect(berkeley).toHaveTextContent('CC BY-NC 4.0 International');
    expect(berkeley).toHaveTextContent('non-commercial use only');
    expect(within(table).getByRole('row', { name: /PRIMAP-hist/ })).toHaveTextContent('Non-commercial use only');
    expect(within(table).queryByText(/crosswalk/i)).not.toBeInTheDocument();
    expect(within(table).getByRole('row', { name: /monthly mean/ })).toHaveTextContent('Latest CO₂ reading');
    expect(within(table).getByRole('row', { name: /monthly mean/ })).not.toHaveTextContent('joined at 1959');
    expect(within(table).getAllByRole('row')).toHaveLength(1 + 5); // header + five sources
  });

  it('shows the baselines by view and the computed temperature offset', () => {
    render(<MethodologySection meta={META} metaFailed={false} splice={SPLICE} />);
    const table = screen.getByRole('table', { name: 'Baselines by view' });
    expect(within(table).getByRole('row', { name: /Long-run CO₂ relationship/ })).toHaveTextContent('1850–1900 reference');
    expect(within(table).getByRole('row', { name: /Overview, Historical Trends/ })).toHaveTextContent('1990 = 100');
    expect(screen.getByText(/computed from the Berkeley Earth record itself \(51 years\).*-0\.306 °C/)).toBeInTheDocument();
  });

  it('gives the API\'s two-totals note verbatim, why the series differ, and the splice figures from the concentration response', () => {
    render(<MethodologySection meta={META} metaFailed={false} splice={SPLICE} />);
    // the response's note, whole and unaltered (the fixture is the API's constant word for word, so this is checked against fixed text as well as the prop)
    const note = screen.getByText(/^Two different global totals are used on purpose\./);
    expect(note.textContent).toBe(META.two_global_totals);
    expect(note.textContent).toContain('so country shares sum to 100% of territorial emissions. The two totals therefore differ by the international transport line, published as its own indicator.');
    expect(screen.getByText(/differ in scope, method, the treatment of bunker fuels/)).toBeInTheDocument();
    expect(screen.getByText(/Law Dome ice-core values before 1959 and Mauna Loa from 1959\. Over the overlap years 1959–2004 the two records differ by up to 3\.9 ppm, and by 0\.28 ppm at the splice itself\./)).toBeInTheDocument();
  });

  it('says the sources could not be loaded, once, and leaves out the API-dependent parts (never blank cells)', () => {
    render(<MethodologySection meta={null} metaFailed splice={null} />);
    expect(screen.getByText('The sources, licences and data vintages could not be loaded right now. The baseline rules below do not depend on them.')).toBeInTheDocument();
    expect(screen.queryByText(/baselines could not be loaded/)).not.toBeInTheDocument();
    expect(screen.queryByRole('table', { name: 'Sources' })).not.toBeInTheDocument();
    expect(screen.queryByText('Two global totals')).not.toBeInTheDocument();
    expect(screen.queryByText(/^The \d{4} splice$/)).not.toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Baselines by view' })).toBeInTheDocument(); // the app's own rules need no data
  });

  it('omits the splice note when the concentration response documents none', () => {
    render(<MethodologySection meta={META} metaFailed={false} splice={null} />);
    expect(screen.queryByText(/^The \d{4} splice$/)).not.toBeInTheDocument();
  });
});
