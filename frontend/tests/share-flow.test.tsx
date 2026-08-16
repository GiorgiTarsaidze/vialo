import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ResultActions from '../src/components/ResultActions';
import type { ItineraryResponse } from '../src/lib/types';

vi.mock('../src/lib/api-client', () => ({
  createShare: vi.fn(),
  deleteShare: vi.fn(),
  ApiClientError: class ApiClientError extends Error {},
}));

import { createShare } from '../src/lib/api-client';

const result: ItineraryResponse = {
  schemaVersion: 1,
  requestId: 'request-1',
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
    placeId: 'origin', displayName: 'Origin', formattedAddress: 'Origin address',
    location: { latitude: 45.4, longitude: 12.3 }, primaryType: null,
    timeZoneId: 'Europe/Rome', photos: [],
  },
  stops: [], timeline: [], droppedStops: [],
  comparison: { status: 'unavailable', reasonCode: 'NO_DATA' },
  mapsHandoff: {
    fullRouteUrl: 'https://www.google.com/maps/dir/?api=1',
    fullRouteUniversallySupported: true,
    browserSafeParts: [], warningCode: null, errorCode: null,
  },
  totals: { visitSeconds: 0, travelSeconds: 0, waitSeconds: 0, elapsedSeconds: 0 },
  diagnostics: [],
  shareProof: { expiresAt: '2026-08-18T10:00:00Z', hmac: 'proof' },
};

describe('ResultActions sharing', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(createShare).mockReset();
  });

  it('creates and copies the link on the first activation', async () => {
    vi.mocked(createShare).mockResolvedValue({
      shareId: 'share-1',
      shareUrl: 'https://vialo.place/r/share-1',
      deletionToken: 'delete-token',
    });
    const user = userEvent.setup();
    const clipboardSpy = vi
      .spyOn(navigator.clipboard, 'writeText')
      .mockResolvedValue(undefined);
    render(<ResultActions result={result} />);

    await user.click(screen.getByRole('button', { name: 'Copy share link' }));

    await waitFor(() => {
      expect(clipboardSpy).toHaveBeenCalledWith(
        'https://vialo.place/r/share-1',
      );
    });
    expect(screen.getByRole('button', { name: 'Link copied!' })).toBeInTheDocument();
    expect(localStorage.getItem('vialo_share_share-1')).toBe('delete-token');
  });
});
