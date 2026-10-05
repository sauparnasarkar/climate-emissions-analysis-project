import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse } from '../../api/correlationTypes';
import { buildDerivation } from '../../lib/derivation';
import { HEADLINE_PAIR } from '../../test/climateFixtures';
import { DerivationAccordion } from './DerivationAccordion';

afterEach(cleanup);
const mount = (resp: CorrelationEmissionsTemperatureResponse = HEADLINE_PAIR) => render(<DerivationAccordion derivation={buildDerivation(resp)!} />);
const step = (n: number) => screen.getAllByRole('button')[n - 1];
const panel = (n: number) => document.getElementById(step(n).getAttribute('aria-controls')!) as HTMLElement;

describe('DerivationAccordion', () => {
  it('has the heading, says every figure is read from the pipeline output, and lists the seven steps in order, numbered', () => {
    mount();
    expect(screen.getByRole('heading', { level: 3, name: 'How this number was derived' })).toBeInTheDocument();
    expect(screen.getByText('Every figure below is read from the pipeline output.')).toBeInTheDocument();
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
      '01What is regressed on what', '02Uncertainty', '03How sensitive the slope is', '04Stability', '05Comparison with the IPCC range', '06Data, licences and attribution', '07What this is not',
    ]);
  });

  it('opens the first step by default and only one at a time', () => {
    mount();
    expect(step(1)).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-expanded') === 'true')).toHaveLength(1);
    fireEvent.click(step(4));
    expect(step(4)).toHaveAttribute('aria-expanded', 'true');
    expect(step(1)).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-expanded') === 'true')).toHaveLength(1);
    fireEvent.click(step(4)); // and it can be closed again
    expect(screen.getAllByRole('button').filter((b) => b.getAttribute('aria-expanded') === 'true')).toHaveLength(0);
  });

  it('step 1 says what is regressed on what, with the response\'s own method and descriptions', () => {
    mount();
    const body = within(panel(1));
    expect(body.getByText(/Total anthropogenic CO2 \(fossil \+ cement \+ land-use change\)\. The slope is the change in/)).toBeInTheDocument();
    expect(body.getByText(/0\.520 °C per 1,000 GtCO2, with R² 0\.90/)).toBeInTheDocument();
    expect(body.getByText('Method: OLS with intercept; Newey-West (HAC) standard errors.')).toBeInTheDocument();
    expect(body.getByText(/analog to the IPCC's TCRE \(AR6 best estimate about 0\.45.*not a restatement of it/)).toBeInTheDocument();
  });

  it('step 2 gives the OLS and HAC errors, the autocorrelation, the API\'s lag rule and the bandwidth table', () => {
    mount();
    fireEvent.click(step(2));
    const body = within(panel(2));
    expect(body.getByText(/ordinary least-squares standard error of the slope is 0\.013; the Newey–West \(HAC\) standard error is 0\.020, because the residuals are autocorrelated \(lag-1 0\.55, Durbin–Watson 0\.89\)\. Ignoring that autocorrelation would understate the uncertainty\./)).toBeInTheDocument();
    expect(body.getByText('maxlags = floor(1.5 * n^(1/3)); Bartlett kernel; 95% CI from the HAC standard error (normal).')).toBeInTheDocument();
    const rows = body.getAllByRole('row').slice(1).map((r) => r.textContent);
    expect(rows).toEqual(['40.0180.485–0.554', '80.0200.480–0.559', '160.0230.475–0.565']);
  });

  it('step 3 shows the land-use scaling and the weight scan with the API\'s caution about not choosing a weight', () => {
    mount();
    fireEvent.click(step(3));
    const body = within(panel(3));
    expect(body.getByRole('table', { name: 'Scaling the land-use emissions' })).toBeInTheDocument();
    expect(within(body.getByRole('table', { name: /Weight on land-use CO₂, holdout from 2000/ })).getAllByRole('row')).toHaveLength(3);
    expect(body.getByText(/not to choose a weight/)).toBeInTheDocument();
  });

  it('step 4 gives the bootstrap, block lengths, holdouts (vs the naive baseline) and the API\'s summary and note', () => {
    mount();
    fireEvent.click(step(4));
    const body = within(panel(4));
    expect(body.getByText(/Estimated from later start years \(1850, 1900, 1950, 1970\) the slope ranges from 0\.520 to 0\.638/)).toBeInTheDocument();
    expect(body.getByText(/95% interval 0\.473–0\.568 with 10-year blocks, against 0\.480–0\.559 from the Newey–West standard errors/)).toBeInTheDocument();
    expect(within(body.getByRole('table', { name: /Decade holdouts/ })).getByRole('row', { name: /1980/ })).toHaveTextContent('0.229');
    expect(body.getByText('These are published as measured; no pass/fail judgement is made.')).toBeInTheDocument();
  });

  it('step 5 compares with AR6 in numbers from the response, and step 6 lists each source\'s licence and citations verbatim', () => {
    mount();
    fireEvent.click(step(5));
    expect(within(panel(5)).getByText(/very likely range for the transient climate response to cumulative emissions is 0\.27–0\.63 °C per 1,000 GtCO2, best estimate 0\.45\. This slope \(0\.520\) lies within that range and is 1\.15× the best estimate; its 95% interval overlaps the range\./)).toBeInTheDocument();
    fireEvent.click(step(6));
    const body = within(panel(6));
    expect(body.getByText(/^CC BY-NC 4\.0 International/)).toBeInTheDocument();
    expect(body.getByText(/Land-use CO2 data originates from the Global Carbon Project via OWID/)).toBeInTheDocument();
    expect(body.getByText(/Friedlingstein, P\. et al\./)).toBeInTheDocument();
  });

  it('step 7 is the fixed "what this is not" list: not a climate model, not proof of cause, not TCRE, no country attribution', () => {
    mount();
    fireEvent.click(step(7));
    const text = panel(7).textContent!;
    expect(text).toMatch(/not a climate model/i);
    expect(text).toMatch(/context, not proof of cause/);
    expect(text).toMatch(/not a restatement of it/);
    expect(text).toMatch(/no warming is attributed to a country/);
  });

  it('never shows the fit-quality note (decision 41: its wording waits for the owner), even with every step open in turn', () => {
    mount();
    for (let i = 1; i <= 7; i++) fireEvent.click(step(i));
    expect(document.body.textContent).not.toMatch(/HELD FOR THE OWNER/);
  });

  it('leaves out a step whose data is missing and renumbers the rest, keeping the closing step', () => {
    const ctx = { ...(HEADLINE_PAIR.fit_context as Record<string, unknown>) };
    delete ctx.stability;
    delete ctx.ar6_reference;
    mount({ ...HEADLINE_PAIR, fit_context: ctx, attribution: [] } as unknown as CorrelationEmissionsTemperatureResponse);
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['01What is regressed on what', '02Uncertainty', '03How sensitive the slope is', '04What this is not']);
  });
});
