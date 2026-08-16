import { describe, it, expect } from 'vitest';
import { getMarkerData } from '../src/components/SelectionMap';
import type { PlaceRef } from '../src/lib/types';

describe('SelectionMap getMarkerData', () => {
  it('returns empty array when both are null', () => {
    expect(getMarkerData(null, null)).toEqual([]);
  });

  it('returns empty when origin has no location', () => {
    const origin: PlaceRef = { placeId: 'p1', displayName: 'Hotel', formattedAddress: 'Addr' };
    expect(getMarkerData(origin, null)).toEqual([]);
  });

  it('returns start marker when origin has location', () => {
    const origin: PlaceRef = {
      placeId: 'p1',
      displayName: 'Hotel',
      formattedAddress: 'Addr',
      location: { latitude: 45.4, longitude: 12.3 },
    };
    const markers = getMarkerData(origin, null);
    expect(markers).toHaveLength(1);
    expect(markers[0]!.type).toBe('start');
    expect(markers[0]!.label).toBe('S');
    expect(markers[0]!.lat).toBe(45.4);
    expect(markers[0]!.lng).toBe(12.3);
  });

  it('returns end marker when only destination has location', () => {
    const dest: PlaceRef = {
      placeId: 'p2',
      displayName: 'Station',
      formattedAddress: 'Addr 2',
      location: { latitude: 45.5, longitude: 12.4 },
    };
    const markers = getMarkerData(null, dest);
    expect(markers).toHaveLength(1);
    expect(markers[0]!.type).toBe('end');
    expect(markers[0]!.label).toBe('E');
  });

  it('returns both markers when origin and destination differ', () => {
    const origin: PlaceRef = {
      placeId: 'p1',
      displayName: 'Hotel',
      formattedAddress: 'Addr 1',
      location: { latitude: 45.4, longitude: 12.3 },
    };
    const dest: PlaceRef = {
      placeId: 'p2',
      displayName: 'Station',
      formattedAddress: 'Addr 2',
      location: { latitude: 45.5, longitude: 12.4 },
    };
    const markers = getMarkerData(origin, dest);
    expect(markers).toHaveLength(2);
    expect(markers[0]!.type).toBe('start');
    expect(markers[1]!.type).toBe('end');
  });

  it('returns single same marker when origin and destination are the same place', () => {
    const origin: PlaceRef = {
      placeId: 'p1',
      displayName: 'Hotel',
      formattedAddress: 'Addr',
      location: { latitude: 45.4, longitude: 12.3 },
    };
    const dest: PlaceRef = {
      placeId: 'p1',
      displayName: 'Hotel',
      formattedAddress: 'Addr',
      location: { latitude: 45.4, longitude: 12.3 },
    };
    const markers = getMarkerData(origin, dest);
    expect(markers).toHaveLength(1);
    expect(markers[0]!.type).toBe('same');
    expect(markers[0]!.label).toBe('S/E');
    expect(markers[0]!.title).toContain('Start & End');
  });
});
