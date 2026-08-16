import { describe, expect, it } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from '../src/lib/itinerary-response.schema.json';
import type { ItineraryResponse } from '../src/lib/types';

const fixture: ItineraryResponse = {
  schemaVersion: 1,
  requestId: 'contract-request',
  status: 'complete',
  locality: { name: 'Venice', timeZoneId: 'Europe/Rome' },
  travelMode: 'WALK',
  window: {
    start: '2026-08-18T09:00:00+02:00',
    end: '2026-08-18T17:00:00+02:00',
    localStart: '09:00',
    localEnd: '17:00',
    date: '2026-08-18',
  },
  origin: {
    placeId: 'origin',
    displayName: 'Origin',
    formattedAddress: 'Origin address',
    location: { latitude: 45.4, longitude: 12.3 },
    primaryType: null,
    timeZoneId: 'Europe/Rome',
    photos: [],
    rating: null,
    userRatingCount: null,
  },
  destination: null,
  stops: [{
    candidateIndex: 0,
    name: 'Verified stop',
    category: 'landmark',
    priority: 1,
    visitDurationMinutes: 30,
    durationSource: 'model_estimate',
    place: {
      placeId: 'stop',
      displayName: 'Verified stop',
      formattedAddress: 'Stop address',
      location: { latitude: 45.41, longitude: 12.31 },
      primaryType: 'tourist_attraction',
      timeZoneId: 'Europe/Rome',
      photos: [],
      rating: 4.5,
      userRatingCount: 1000,
    },
    hoursSource: 'current',
    openIntervals: [{
      start: '2026-08-18T09:00:00+02:00',
      end: '2026-08-18T18:00:00+02:00',
      localStart: '09:00',
      localEnd: '18:00',
    }],
  }],
  timeline: [{
    type: 'visit',
    stopIndex: 1,
    arrival: '2026-08-18T09:10:00+02:00',
    departure: '2026-08-18T09:40:00+02:00',
    durationMinutes: 30,
    intervalUsed: {
      start: '2026-08-18T09:00:00+02:00',
      end: '2026-08-18T18:00:00+02:00',
      localStart: '09:00',
      localEnd: '18:00',
    },
  }],
  droppedStops: [],
  comparison: { status: 'unavailable', reasonCode: 'TEST' },
  mapsHandoff: {
    fullRouteUrl: 'https://www.google.com/maps/dir/?api=1',
    fullRouteUniversallySupported: true,
    browserSafeParts: [],
    warningCode: null,
    errorCode: null,
  },
  totals: {
    visitSeconds: 1800,
    travelSeconds: 600,
    waitSeconds: 0,
    elapsedSeconds: 2400,
  },
  diagnostics: [],
  shareProof: {
    expiresAt: '2026-08-18T10:00:00Z',
    hmac: 'test-proof',
  },
};

const validationSchema = JSON.parse(
  JSON.stringify(schema, (key, value) => key === 'discriminator' ? undefined : value),
) as object;
const ajv = new Ajv2020({
  allErrors: true,
  strict: true,
  strictTypes: false,
});
addFormats(ajv);
const validate = ajv.compile(validationSchema);

describe('Pydantic frontend contract', () => {
  it('accepts the TypeScript itinerary fixture', () => {
    expect(validate(fixture), JSON.stringify(validate.errors)).toBe(true);
  });

  it('rejects a drifted schema version', () => {
    const drifted = { ...fixture, schemaVersion: 2 };
    expect(validate(drifted)).toBe(false);
  });
});
