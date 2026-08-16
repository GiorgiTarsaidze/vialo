import { describe, it, expect } from 'vitest';
import { formatDuration, formatDistance, formatTime, decodePolyline, travelModeLabel } from '../src/lib/format';

describe('formatDuration', () => {
  it('formats seconds under 60 min', () => {
    expect(formatDuration(360)).toBe('6 min');
    expect(formatDuration(0)).toBe('0 min');
    expect(formatDuration(59 * 60)).toBe('59 min');
  });

  it('formats hours and minutes', () => {
    expect(formatDuration(3600)).toBe('1 hr');
    expect(formatDuration(3600 + 4 * 60)).toBe('1 hr 04 min');
    expect(formatDuration(2 * 3600 + 30 * 60)).toBe('2 hr 30 min');
  });
});

describe('formatDistance', () => {
  it('formats meters under 1000', () => {
    expect(formatDistance(500)).toBe('500 m');
    expect(formatDistance(999)).toBe('999 m');
  });

  it('formats km with one decimal', () => {
    expect(formatDistance(1000)).toBe('1.0 km');
    expect(formatDistance(5100)).toBe('5.1 km');
    expect(formatDistance(8400)).toBe('8.4 km');
  });
});

describe('formatTime', () => {
  it('preserves the place-local wall time encoded in the ISO value', () => {
    expect(formatTime('2024-01-01T14:05:00+04:00')).toBe('14:05');
    expect(formatTime('2024-01-01T09:30:00-05:00')).toBe('09:30');
  });

  it('returns a safe placeholder for malformed values', () => {
    expect(formatTime('not-a-date')).toBe('--:--');
  });
});

describe('decodePolyline', () => {
  it('decodes a simple Google polyline', () => {
    const encoded = '_p~iF~ps|U_ulLnnqC_mqNvxq`@';
    const points = decodePolyline(encoded);
    expect(points.length).toBe(3);
    expect(points[0]!.lat).toBeCloseTo(38.5, 1);
    expect(points[0]!.lng).toBeCloseTo(-120.2, 1);
  });

  it('returns empty for empty string', () => {
    expect(decodePolyline('')).toEqual([]);
  });
});

describe('travelModeLabel', () => {
  it('returns walking/driving', () => {
    expect(travelModeLabel('WALK')).toBe('walking');
    expect(travelModeLabel('DRIVE')).toBe('driving');
  });
});
