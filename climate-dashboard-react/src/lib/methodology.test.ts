import { describe, expect, it } from 'vitest';
import type { CorrelationMetaResponse } from '../api/correlationTypes';
import { META } from '../test/climateFixtures';
import { buildSources, buildTemperatureOffset } from './methodology';

describe('buildSources', () => {
  const rows = buildSources(META);

  it('merges a source\'s datasets into one row, leaves out derived metadata, and keeps the API\'s order of first appearance', () => {
    expect(rows.map((r) => r.name)).toEqual([
      'NOAA GML Mauna Loa (1959+) spliced to Law Dome ice-core/firn spline (pre-1959)',
      'Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)',
      'PRIMAP-hist v2.8 (Gütschow & Pflüger)',
      'Berkeley Earth Land/Ocean global temperature (annual)',
    ]);
  });

  it('spans the merged datasets\' coverage and takes the most recent vintage the API states, labelled as published, file date or retrieval', () => {
    const by = Object.fromEntries(rows.map((r) => [r.name.split(' ')[0], r]));
    expect(by.NOAA.coverage).toBe('1750–2026');
    expect(by.NOAA.vintage).toBe('file of 2026-09-09'); // the later of the two
    expect(by.Our.vintage).toBe('retrieved 2026-07-18');
    expect(by['PRIMAP-hist'].vintage).toBe('published 2026-09-29 (v2.8)');
    expect(by.Berkeley.vintage).toBe('file of 2025-01-10');
  });

  it('gives each source\'s licence in the API\'s own words (Berkeley Earth is CC BY 4.0 here), once even when its datasets share it', () => {
    const by = Object.fromEntries(rows.map((r) => [r.name.split(' ')[0], r]));
    expect(by.Berkeley.licences).toEqual(['Berkeley Earth data: CC BY 4.0 (cite Rohde & Hausfather 2020).']);
    expect(by.Our.licences).toHaveLength(1);
    expect(by['PRIMAP-hist'].licences[0]).toMatch(/not yet verified/);
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
