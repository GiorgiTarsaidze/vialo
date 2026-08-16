import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { planItinerary, createShare, getShare, deleteShare, ApiClientError } from '../src/lib/api-client';
import { isItineraryResponse, isCreateShareResponse, isApiError } from '../src/lib/guards';

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function makeMinimalItinerary() {
  return {
    schemaVersion: 1 as const,
    requestId: 'req-123',
    status: 'complete' as const,
    locality: { name: 'Venice', timeZoneId: 'Europe/Rome' },
    travelMode: 'WALK' as const,
    window: { start: '2024-01-01T09:00:00Z', end: '2024-01-01T17:00:00Z', localStart: '09:00', localEnd: '17:00', date: '2024-01-01' },
    origin: { placeId: 'place1', displayName: 'Hotel', formattedAddress: 'Via X', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [] },
    stops: [],
    timeline: [],
    droppedStops: [],
    comparison: { status: 'unavailable' as const, reasonCode: 'NO_DATA' },
    mapsHandoff: { fullRouteUrl: null, fullRouteUniversallySupported: false, browserSafeParts: [], warningCode: null, errorCode: null },
    totals: { visitSeconds: 0, travelSeconds: 0, waitSeconds: 0, elapsedSeconds: 0 },
    diagnostics: [],
    shareProof: null,
  };
}

describe('guards', () => {
  it('isApiError returns true for valid error shape', () => {
    expect(isApiError({ error: { code: 'RATE_LIMITED', message: 'Too many' } })).toBe(true);
  });

  it('isApiError returns false for non-error', () => {
    expect(isApiError({ foo: 'bar' })).toBe(false);
    expect(isApiError(null)).toBe(false);
    expect(isApiError('string')).toBe(false);
  });

  it('isItineraryResponse validates minimal response', () => {
    expect(isItineraryResponse(makeMinimalItinerary())).toBe(true);
  });

  it('isItineraryResponse rejects missing fields', () => {
    expect(isItineraryResponse({})).toBe(false);
    expect(isItineraryResponse({ schemaVersion: 2 })).toBe(false);
  });

  it('isCreateShareResponse validates share response', () => {
    expect(isCreateShareResponse({ shareId: 'abc', shareUrl: 'https://x.com/r/abc', deletionToken: 'tok' })).toBe(true);
    expect(isCreateShareResponse({ shareId: 'abc' })).toBe(false);
  });
});

describe('planItinerary', () => {
  beforeEach(() => mockFetch.mockReset());
  afterEach(() => vi.restoreAllMocks());

  it('sends POST with prompt and returns parsed response', async () => {
    const itinerary = makeMinimalItinerary();
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(itinerary),
    });

    const result = await planItinerary('Venice, 09:00–17:00');
    expect(mockFetch).toHaveBeenCalledWith('/api/itineraries', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ prompt: 'Venice, 09:00–17:00' }),
    }));
    expect(result.requestId).toBe('req-123');
  });

  it('throws ApiClientError on 429 with retry timing', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 429,
      headers: { get: (name: string) => name === 'Retry-After' ? '120' : null },
      json: () => Promise.resolve({ error: { code: 'RATE_LIMITED', message: 'Try later' } }),
    });

    try {
      await planItinerary('test');
      throw new Error('Expected planItinerary to reject');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiClientError);
      expect((error as ApiClientError).code).toBe('RATE_LIMITED');
      expect((error as ApiClientError).retryAfterMs).toBe(120000);
    }
  });

  it('throws on invalid response shape', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ unexpected: true }),
    });

    await expect(planItinerary('test')).rejects.toThrow('unexpected response format');
  });
});

describe('createShare', () => {
  beforeEach(() => mockFetch.mockReset());

  it('sends itinerary with proof', async () => {
    const itinerary = { ...makeMinimalItinerary(), shareProof: { expiresAt: '2024-01-01T10:00:00Z', hmac: 'abc123' } } as const;
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ shareId: 's1', shareUrl: '/r/s1', deletionToken: 'del-tok' }),
    });

    const result = await createShare(itinerary as unknown as import('../src/lib/types').ItineraryResponse);
    expect(result.shareId).toBe('s1');
    expect(result.deletionToken).toBe('del-tok');
  });

  it('throws when no shareProof', async () => {
    const itinerary = makeMinimalItinerary() as unknown as import('../src/lib/types').ItineraryResponse;
    await expect(createShare(itinerary)).rejects.toThrow('no share proof');
  });
});

describe('getShare', () => {
  beforeEach(() => mockFetch.mockReset());

  it('fetches share by id', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(makeMinimalItinerary()),
    });

    const result = await getShare('share-abc');
    expect(mockFetch).toHaveBeenCalledWith('/api/shares/share-abc');
    expect(result.schemaVersion).toBe(1);
  });
});

describe('deleteShare', () => {
  beforeEach(() => mockFetch.mockReset());

  it('sends DELETE with token header', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true, status: 204 });

    await deleteShare('share-abc', 'my-token');
    expect(mockFetch).toHaveBeenCalledWith('/api/shares/share-abc', expect.objectContaining({
      method: 'DELETE',
      headers: { 'X-Share-Delete-Token': 'my-token' },
    }));
  });
});
