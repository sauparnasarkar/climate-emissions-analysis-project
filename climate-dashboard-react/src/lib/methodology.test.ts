import { describe, expect, it } from 'vitest';
import type { CorrelationMetaResponse } from '../api/correlationTypes';
import { META } from '../test/climateFixtures';
import { buildSources, buildTemperatureOffset } from './methodology';

describe('buildSources', () => {
  const rows = buildSources(META);

  it('merges datasets of the same source into one row (OWID, PRIMAP-hist), keeps the monthly NOAA dataset as its own source, leaves out derived metadata, and keeps the API\'s order', () => {
    expect(rows.map((r) => r.name)).toEqual([
      'NOAA GML Mauna Loa (1959+) spliced to Law Dome ice-core/firn spline (pre-1959)',
      'NOAA GML Mauna Loa monthly mean',
      'Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)',
      'PRIMAP-hist v2.8 (Gütschow & Pflüger)',
      'Berkeley Earth Land/Ocean global temperature (annual)',
    ]);
  });

  it('spans merged datasets\' coverage and takes the most recent vintage the API states, labelled as published, file date or retrieval', () => {
    const by = Object.fromEntries(rows.map((r) => [r.name.split(' ')[0], r]));
    expect(rows[0].coverage).toBe('1750–2025'); // the annual spliced record
    expect(rows[1].coverage).toBe('1958–2026'); // the monthly record is its own row
    expect(rows[0].vintage).toBe('file of 2026-09-08');
    expect(by.Our.coverage).toBe('1750–2024');
    expect(by.Our.vintage).toBe('retrieved 2026-07-18');
    expect(by['PRIMAP-hist'].vintage).toBe('published 2026-09-29 (v2.8)');
    expect(by.Berkeley.vintage).toBe('file of 2025-01-10');
  });

  it('gives each source\'s licence in the API\'s own words (Berkeley Earth is CC BY-NC 4.0, non-commercial), once even when its datasets share it', () => {
    const by = Object.fromEntries(rows.map((r) => [r.name.split(' ')[0], r]));
    expect(by.Berkeley.licences).toHaveLength(1);
    expect(by.Berkeley.licences[0]).toMatch(/^CC BY-NC 4\.0 International/);
    expect(by.Berkeley.licences[0]).toMatch(/non-commercial use only/);
    expect(by.Our.licences).toHaveLength(1);
    expect(by['PRIMAP-hist'].licences[0]).toMatch(/not yet verified/);
  });

  it('picks the newest vintage by its date, whatever kind of date it is (a 2025 publication is older than a 2026 file)', () => {
    const merged = buildSources({
      ...META,
      sources: [
        { id: 'primap_a', source: 'Mixed', license: 'x', coverage: [1750, 2024], source_release: { published: '2025-03-01', version: 'v2.7' } },
        { id: 'primap_b', source: 'Mixed', license: 'x', coverage: [1750, 2024], source_release: { http_last_modified: '2026-01-15T00:00:00+00:00' } },
        { id: 'primap_c', source: 'Mixed', license: 'x', coverage: [1750, 2024], retrieved_at: '2025-12-31T00:00:00+00:00' },
      ],
    } as unknown as CorrelationMetaResponse);
    expect(merged[0].vintage).toBe('file of 2026-01-15'); // 'published…' sorts after 'file…' as text, but is older
    const newerPublication = buildSources({ ...META, sources: [
      { id: 'primap_a', source: 'Mixed', license: 'x', source_release: { published: '2026-09-29', version: 'v2.8' } },
      { id: 'primap_b', source: 'Mixed', license: 'x', source_release: { http_last_modified: '2026-01-15T00:00:00+00:00' } },
    ] } as unknown as CorrelationMetaResponse);
    expect(newerPublication[0].vintage).toBe('published 2026-09-29 (v2.8)'); // keeps the chosen entry's label and version
  });

  it('says only the annual NOAA record is joined to the ice-core record (no typed-in year); the monthly record is the latest reading', () => {
    expect(rows[0].usedFor).toBe('Atmospheric CO₂ (joined to the ice-core record)');
    expect(rows[0].usedFor).not.toMatch(/\d{4}/);
    expect(rows[1].usedFor).toBe('Latest CO₂ reading (Mauna Loa monthly)');
    expect(rows[1].usedFor).not.toMatch(/1959/);
    expect(rows[1].licences).toEqual(['NOAA GML: public domain, citation requested.']);
  });

  it('adds only a short used-for phrase of its own, none for a source it does not know', () => {
    expect(rows.find((r) => r.name.startsWith('PRIMAP'))!.usedFor).toMatch(/All-gas view/);
    const unknown = buildSources({ ...META, sources: [{ id: 'mystery', source: 'Mystery', license: 'x', coverage: [2000, 2001] }] } as unknown as CorrelationMetaResponse);
    expect(unknown[0].usedFor).toBeNull();
    expect(unknown[0].vintage).toBeNull();
  });

  it('is empty without a response or sources', () => {
    expect(buildSources(null)).toEqual([]);
    expect(buildSources({ ...META, sources: [] })).toEqual([]);
  });
});

describe('buildTemperatureOffset', () => {
  it('reads the computed 1850–1900 offset from /meta', () => {
    expect(buildTemperatureOffset(META)).toEqual({ valueC: -0.3062, years: 51, from: 1850, to: 1900 });
  });
  it('is null when it is not published or incomplete', () => {
    expect(buildTemperatureOffset(null)).toBeNull();
    expect(buildTemperatureOffset({ ...META, temperature_offset: null })).toBeNull();
    expect(buildTemperatureOffset({ ...META, temperature_offset: { value_c: -0.3 } } as unknown as CorrelationMetaResponse)).toBeNull();
  });
});
