import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import SharedItineraryView from '../src/components/SharedItineraryView';

vi.mock('../src/lib/api-client', () => ({
  getShare: vi.fn(),
  createShare: vi.fn(),
  deleteShare: vi.fn(),
  ApiClientError: class ApiClientError extends Error {
    code: string;
    statusCode: number;
    constructor(code: string, message: string, statusCode: number) {
      super(message);
      this.code = code;
      this.statusCode = statusCode;
    }
  },
}));

import { getShare, deleteShare, ApiClientError } from '../src/lib/api-client';

const mockGetShare = getShare as ReturnType<typeof vi.fn>;
const mockDeleteShare = deleteShare as ReturnType<typeof vi.fn>;

function makeItinerary() {
  return {
    schemaVersion: 1,
    requestId: 'r1',
    status: 'complete',
    locality: { name: 'Venice', timeZoneId: 'Europe/Rome' },
    travelMode: 'WALK',
    window: { start: '2024-01-01T09:00:00Z', end: '2024-01-01T17:00:00Z', localStart: '09:00', localEnd: '17:00', date: '2024-01-01' },
    origin: { placeId: 'p1', displayName: 'Hotel', formattedAddress: 'Via X', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [] },
    stops: [],
    timeline: [],
    droppedStops: [],
    comparison: { status: 'unavailable', reasonCode: 'NO_DATA' },
    mapsHandoff: { fullRouteUrl: null, fullRouteUniversallySupported: false, browserSafeParts: [], warningCode: null, errorCode: null },
    totals: { visitSeconds: 0, travelSeconds: 0, waitSeconds: 0, elapsedSeconds: 0 },
    diagnostics: [],
    shareProof: null,
  };
}

function renderWithRoute(shareId: string) {
  return render(
    <MemoryRouter initialEntries={[`/r/${shareId}`]}>
      <Routes>
        <Route path="/r/:shareId" element={<SharedItineraryView />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('SharedItineraryView', () => {
  beforeEach(() => {
    localStorage.clear();
    mockGetShare.mockReset();
    mockDeleteShare.mockReset();
  });

  it('shows loading state initially', () => {
    mockGetShare.mockReturnValue(new Promise(() => {})); // Never resolves
    renderWithRoute('test-share');
    expect(screen.getByText(/Loading shared itinerary/)).toBeInTheDocument();
  });

  it('shows itinerary when loaded', async () => {
    mockGetShare.mockResolvedValueOnce(makeItinerary());
    renderWithRoute('test-share');
    await waitFor(() => {
      expect(screen.getByText(/Shared itinerary/)).toBeInTheDocument();
    });
  });

  it('shows not found state on SHARE_NOT_FOUND error', async () => {
    mockGetShare.mockRejectedValueOnce(new ApiClientError('SHARE_NOT_FOUND', 'Not found', 404));
    renderWithRoute('expired-share');
    await waitFor(() => {
      expect(screen.getByText(/no longer available/)).toBeInTheDocument();
    });
    expect(screen.getByText(/30 days/)).toBeInTheDocument();
    expect(screen.getByText(/Build a new day/)).toBeInTheDocument();
  });

  it('transitions a creator to the unavailable state after deleting the shared link', async () => {
    localStorage.setItem('vialo_share_creator-share', 'delete-token');
    mockGetShare.mockResolvedValueOnce(makeItinerary());
    mockDeleteShare.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    renderWithRoute('creator-share');
    const deleteButton = await screen.findByRole('button', { name: 'Delete shared link' });
    await user.click(deleteButton);
    await user.click(screen.getByRole('button', { name: 'Confirm deletion' }));

    await waitFor(() => {
      expect(screen.getByText(/no longer available/)).toBeInTheDocument();
    });
    expect(mockDeleteShare).toHaveBeenCalledWith('creator-share', 'delete-token');
    expect(localStorage.getItem('vialo_share_creator-share')).toBeNull();
    expect(screen.queryByText(/Shared itinerary/)).not.toBeInTheDocument();
  });
});
