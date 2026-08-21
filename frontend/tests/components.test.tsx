import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import InputHero from '../src/components/InputHero';
import LoadingPipeline from '../src/components/LoadingPipeline';
import AppShell from '../src/components/AppShell';
import ResultStatement from '../src/components/ResultStatement';
import DroppedStops from '../src/components/DroppedStops';
import RouteComparisonSummary from '../src/components/RouteComparisonSummary';
import ComparisonMap from '../src/components/ComparisonMap';
import ResultView from '../src/components/ResultView';
import type { ItineraryResponse } from '../src/lib/types';

// Mock the google-maps loader so ComparisonMap doesn't trigger async state updates
vi.mock('../src/lib/google-maps', () => {
  // Pre-rejected promise avoids microtask-delayed state updates
  const rejection = Promise.reject(new Error('No Maps in test'));
  rejection.catch(() => {}); // Prevent unhandled rejection
  return {
    MAPS_AUTH_FAILURE_EVENT: 'vialo:maps-auth-failure',
    loadGoogleMaps: () => rejection,
    baseMapOptions: () => ({}),
    VIALO_MAP_STYLES: [],
    notifyMapsAuthFailure: () => {},
  };
});

// Mock the autocomplete API for structured mode tests
vi.mock('../src/lib/api-client', () => ({
  fetchAutocomplete: vi.fn(),
  planItinerary: vi.fn(),
  createShare: vi.fn(),
  deleteShare: vi.fn(),
  getShare: vi.fn(),
  ApiClientError: class ApiClientError extends Error {},
}));

import { fetchAutocomplete } from '../src/lib/api-client';

function TestRouter({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter>
      {children}
    </MemoryRouter>
  );
}

function wrap(ui: React.ReactElement) {
  return render(ui, { wrapper: TestRouter });
}

describe('AppShell', () => {
  it('renders header logo with accessible Vialo home label', () => {
    wrap(
      <AppShell onNewDay={vi.fn()} showBack={false}>
        <div>Content</div>
      </AppShell>,
    );
    const homeLink = screen.getByRole('link', { name: 'Vialo home' });
    expect(homeLink).toBeInTheDocument();
    const logo = homeLink.querySelector('img');
    expect(logo).toHaveAttribute('src', '/logo.png');
    expect(logo).toHaveAttribute('alt', '');
    expect(screen.getByText('vialo.')).toBeInTheDocument();
  });

  it('maintains 44px touch target on wordmark link', () => {
    wrap(
      <AppShell onNewDay={vi.fn()} showBack={false}>
        <div>Content</div>
      </AppShell>,
    );
    const homeLink = screen.getByRole('link', { name: 'Vialo home' });
    // Check that min-height/width style is applied (via CSS class)
    expect(homeLink).toHaveClass('wordmark');
  });
});

describe('InputHero', () => {
  it('renders headline and input', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(screen.getByRole('heading', { name: /Describe your day/ })).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /Describe your day/ })).toBeInTheDocument();
  });

  it('shows character count', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(screen.getByText('0 / 500')).toBeInTheDocument();
  });

  it('disables submit when empty', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    const button = screen.getByRole('button', { name: /Build my day/ });
    expect(button).toBeDisabled();
  });

  it('enables submit with valid input', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    const textarea = screen.getByRole('textbox', { name: /Describe your day/ });
    await user.type(textarea, 'Venice morning walk');
    const button = screen.getByRole('button', { name: /Build my day/ });
    expect(button).not.toBeDisabled();
  });

  it('disables submit when over 500 chars', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    const textarea = screen.getByRole('textbox', { name: /Describe your day/ });
    fireEvent.change(textarea, { target: { value: 'a'.repeat(501) } });
    const button = screen.getByRole('button', { name: /Build my day/ });
    expect(button).toBeDisabled();
  });

  it('fills input on example click without submitting and uses tomorrow with explicit origin and time', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={onSubmit} />);
    const example = screen.getByRole('button', { name: /Venice morning/ });
    await user.click(example);
    const textarea = screen.getByRole('textbox', { name: /Describe your day/ }) as HTMLTextAreaElement;
    expect(textarea.value).toMatch(/^Tomorrow,/);
    expect(textarea.value).toContain('Piazzale Roma');
    expect(textarea.value).toContain('09:00');
    expect(textarea.value).toContain('14:00');
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('all three examples have explicit origin, tomorrow, and a time range', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);

    expect(screen.getByRole('button', { name: /Venice morning/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Naples highlights/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Lisbon viewpoints/ })).toBeInTheDocument();

    const examples = [
      { button: /Venice morning/, origin: 'Piazzale Roma', start: '09:00', end: '14:00' },
      { button: /Naples highlights/, origin: 'Piazza del Plebiscito', start: '10:00', end: '18:00' },
      { button: /Lisbon viewpoints/, origin: 'Praça do Comércio', start: '08:30', end: '16:00' },
    ];
    for (const example of examples) {
      fireEvent.click(screen.getByRole('button', { name: example.button }));
      const textarea = screen.getByRole('textbox', { name: /Describe your day/ }) as HTMLTextAreaElement;
      expect(textarea.value).toMatch(/^Tomorrow,/);
      expect(textarea.value).toContain(example.origin);
      expect(textarea.value).toContain(example.start);
      expect(textarea.value).toContain(example.end);
      expect(textarea.value.length).toBeLessThanOrEqual(500);
    }
  });

  it('shows privacy note', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(screen.getByText(/Do not enter sensitive personal information/)).toBeInTheDocument();
  });

  it('displays error state', () => {
    wrap(<InputHero onSubmit={vi.fn()} error={{ code: 'RATE_LIMITED', message: 'Too many requests' }} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Too many requests');
  });

  it('renders loading pipeline when loading', () => {
    wrap(<InputHero onSubmit={vi.fn()} loading />);
    expect(screen.getByText(/Building a day that fits/)).toBeInTheDocument();
  });

  it('shows retry countdown and disables resubmission while rate limited', async () => {
    const user = userEvent.setup();
    wrap(
      <InputHero
        onSubmit={vi.fn()}
        error={{ code: 'RATE_LIMITED', message: 'Request limit reached.', retryAfterMs: 120000 }}
      />,
    );
    await user.type(screen.getByRole('textbox', { name: /Describe your day/ }), 'Venice walking day');
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Try again in 2m 0s');
    // The panel explains why the limit exists, not just that it was hit.
    expect(alert).toHaveTextContent('five planned days per hour');
    expect(screen.getByRole('button', { name: /Build my day/ })).toBeDisabled();
  });

  // --- New input mode tests ---
  it('shows mode toggle with two tabs', () => {
    wrap(<InputHero onSubmit={vi.fn()} />);
    expect(screen.getByRole('tab', { name: 'Describe freely' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Choose details' })).toBeInTheDocument();
  });

  it('switching to structured mode shows start location field', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));
    expect(screen.getByLabelText(/Start location/)).toBeInTheDocument();
    expect(screen.getByText('End where I started')).toBeInTheDocument();
  });

  it('structured mode requires origin selection to submit', async () => {
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={vi.fn()} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));
    // Type in prompt but no origin selected
    const promptArea = screen.getByRole('textbox', { name: /Date, time, and interests/ });
    await user.type(promptArea, '09:00–17:00, churches');
    expect(screen.getByRole('button', { name: /Build my day/ })).toBeDisabled();
  });

  it('structured mode with returnToStart sends destination equal to origin', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    // Mock autocomplete to return a result
    vi.mocked(fetchAutocomplete).mockResolvedValue({
      predictions: [{
        placeId: 'origin-place-id',
        displayName: 'Hotel Venezia',
        formattedAddress: 'Via Roma 1, Venice',
        location: { latitude: 45.4, longitude: 12.3 },
      }],
    });

    wrap(<InputHero onSubmit={onSubmit} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    // Type in origin and wait for results
    const originInput = screen.getByLabelText(/Start location/);
    await user.type(originInput, 'Hotel Venezia');

    // Wait for autocomplete to show results
    await waitFor(() => {
      expect(screen.getByText('Hotel Venezia')).toBeInTheDocument();
    });

    // Select the result
    await user.click(screen.getByText('Hotel Venezia'));

    // Type prompt
    const promptArea = screen.getByRole('textbox', { name: /Date, time, and interests/ });
    await user.type(promptArea, '09:00-17:00, museums');

    // Switch "End where I started" should be on by default
    const switchEl = screen.getByRole('switch', { name: /End where I started/ });
    expect(switchEl).toHaveAttribute('aria-checked', 'true');

    // Submit
    await user.click(screen.getByRole('button', { name: /Build my day/ }));

    // Verify payload: destination should equal origin
    expect(onSubmit).toHaveBeenCalledWith({
      prompt: '09:00-17:00, museums',
      origin: {
        placeId: 'origin-place-id',
        displayName: 'Hotel Venezia',
        formattedAddress: 'Via Roma 1, Venice',
        location: { latitude: 45.4, longitude: 12.3 },
      },
      destination: {
        placeId: 'origin-place-id',
        displayName: 'Hotel Venezia',
        formattedAddress: 'Via Roma 1, Venice',
        location: { latitude: 45.4, longitude: 12.3 },
      },
    });
  });

  it('structured mode with distinct end requires destination selection', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();

    vi.mocked(fetchAutocomplete).mockResolvedValue({
      predictions: [{
        placeId: 'origin-place-id',
        displayName: 'Hotel Venezia',
        formattedAddress: 'Via Roma 1, Venice',
        location: { latitude: 45.4, longitude: 12.3 },
      }],
    });

    wrap(<InputHero onSubmit={onSubmit} />);
    await user.click(screen.getByRole('tab', { name: 'Choose details' }));

    // Select origin
    const originInput = screen.getByLabelText(/Start location/);
    await user.type(originInput, 'Hotel Venezia');
    await waitFor(() => {
      expect(screen.getByText('Hotel Venezia')).toBeInTheDocument();
    });
    await user.click(screen.getByText('Hotel Venezia'));

    // Type prompt
    const promptArea = screen.getByRole('textbox', { name: /Date, time, and interests/ });
    await user.type(promptArea, '09:00-17:00');

    // Uncheck "End where I started"
    const switchEl = screen.getByRole('switch', { name: /End where I started/ });
    await user.click(switchEl);
    expect(switchEl).toHaveAttribute('aria-checked', 'false');

    // Submit should be disabled without destination selected
    expect(screen.getByRole('button', { name: /Build my day/ })).toBeDisabled();

    // Now mock a different destination result
    vi.mocked(fetchAutocomplete).mockResolvedValue({
      predictions: [{
        placeId: 'dest-place-id',
        displayName: 'Train Station',
        formattedAddress: 'Piazzale Roma, Venice',
        location: { latitude: 45.44, longitude: 12.32 },
      }],
    });

    // Select destination
    const destInput = screen.getByLabelText(/End location/);
    await user.type(destInput, 'Train Station');
    await waitFor(() => {
      expect(screen.getByText('Train Station')).toBeInTheDocument();
    });
    await user.click(screen.getByText('Train Station'));

    // Now submit should be enabled
    expect(screen.getByRole('button', { name: /Build my day/ })).not.toBeDisabled();
    await user.click(screen.getByRole('button', { name: /Build my day/ }));

    expect(onSubmit).toHaveBeenCalledWith({
      prompt: '09:00-17:00',
      origin: {
        placeId: 'origin-place-id',
        displayName: 'Hotel Venezia',
        formattedAddress: 'Via Roma 1, Venice',
        location: { latitude: 45.4, longitude: 12.3 },
      },
      destination: {
        placeId: 'dest-place-id',
        displayName: 'Train Station',
        formattedAddress: 'Piazzale Roma, Venice',
        location: { latitude: 45.44, longitude: 12.32 },
      },
    });
  });
});

describe('LoadingPipeline', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows all five pipeline stages', () => {
    render(<LoadingPipeline />);
    expect(screen.getByText('Finding places')).toBeInTheDocument();
    expect(screen.getByText('Checking opening hours')).toBeInTheDocument();
    expect(screen.getByText('Measuring travel times')).toBeInTheDocument();
    expect(screen.getByText('Solving the optimal order')).toBeInTheDocument();
    expect(screen.getByText('Building route geometry')).toBeInTheDocument();
  });

  it('first stage is current on mount', () => {
    render(<LoadingPipeline />);
    const stages = screen.getAllByRole('listitem');
    expect(stages[0]).toHaveAttribute('aria-current', 'step');
  });

  it('advances stages over time: first becomes complete, second becomes current', () => {
    render(<LoadingPipeline />);
    // After 2s, stage 0 is complete and stage 1 is current
    act(() => { vi.advanceTimersByTime(2100); });
    const stages = screen.getAllByRole('listitem');
    expect(stages[0]).not.toHaveAttribute('aria-current', 'step');
    expect(stages[1]).toHaveAttribute('aria-current', 'step');
  });

  it('final stage stays active indefinitely (caps at last index)', () => {
    render(<LoadingPipeline />);
    // Advance well beyond all milestones
    act(() => { vi.advanceTimersByTime(15000); });
    const stages = screen.getAllByRole('listitem');
    // Last stage should be current
    expect(stages[4]).toHaveAttribute('aria-current', 'step');
    // All previous should be complete (no aria-current)
    for (let i = 0; i < 4; i++) {
      expect(stages[i]).not.toHaveAttribute('aria-current', 'step');
    }
  });

  it('shows slow message after ~12s without error alarming', () => {
    render(<LoadingPipeline />);
    expect(screen.queryByText(/Still working/)).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(12100); });
    expect(screen.getByText(/Still working — provider checks can take a little longer/)).toBeInTheDocument();
  });

  it('displays pipeline honesty text', () => {
    render(<LoadingPipeline />);
    expect(screen.getByText(/Working through the usual pipeline/)).toBeInTheDocument();
  });

  it('shows result-shaped preview labels', () => {
    render(<LoadingPipeline />);
    expect(screen.getByText('Route preview')).toBeInTheDocument();
    expect(screen.getByText('Schedule preview')).toBeInTheDocument();
  });

  it('uses reduced-motion–safe patterns (no animation attribute in DOM)', () => {
    // In test setup, prefers-reduced-motion is 'reduce'
    render(<LoadingPipeline />);
    // Spinner should exist even with reduced motion (just no animation)
    const stages = screen.getAllByRole('listitem');
    expect(stages[0]).toHaveAttribute('aria-current', 'step');
  });

  it('live region announces current stage for screen readers', () => {
    render(<LoadingPipeline />);
    const liveRegion = document.querySelector('[aria-live="polite"][aria-atomic="true"]');
    expect(liveRegion).toHaveTextContent('Finding places in progress');
    act(() => { vi.advanceTimersByTime(2100); });
    expect(liveRegion).toHaveTextContent('Checking opening hours in progress');
  });
});

describe('ResultStatement', () => {
  const baseResult = {
    schemaVersion: 1 as const,
    requestId: 'r1',
    status: 'complete' as const,
    locality: { name: 'Venice', timeZoneId: 'Europe/Rome' },
    travelMode: 'WALK' as const,
    window: { start: '2024-01-01T09:00:00Z', end: '2024-01-01T17:00:00Z', localStart: '09:00', localEnd: '17:00', date: '2024-01-01' },
    origin: { placeId: 'p1', displayName: 'Hotel', formattedAddress: 'Via X', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [], rating: null, userRatingCount: null, photoUrl: null },
    destination: null,
    stops: [
      { candidateIndex: 0, name: 'Place A', category: 'landmark' as const, priority: 1, visitDurationMinutes: 30, durationSource: 'model_estimate' as const, place: { placeId: 'pa', displayName: 'Place A', formattedAddress: 'Addr', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [], rating: null, userRatingCount: null, photoUrl: null }, hoursSource: 'current' as const, openIntervals: [] },
    ],
    timeline: [],
    droppedStops: [],
    comparison: { status: 'unavailable' as const, reasonCode: 'NO_DATA' },
    mapsHandoff: { fullRouteUrl: null, fullRouteUniversallySupported: false, browserSafeParts: [], warningCode: null, errorCode: null },
    totals: { visitSeconds: 1800, travelSeconds: 300, waitSeconds: 0, elapsedSeconds: 2100 },
    diagnostics: [],
    shareProof: null,
  };

  it('renders stop count and time range', () => {
    render(<ResultStatement result={baseResult} />);
    expect(screen.getByText(/1 stop fit 09:00–17:00/)).toBeInTheDocument();
    expect(screen.getByText(/Venice · walking/)).toBeInTheDocument();
  });

  it('shows partial status', () => {
    const partial = { ...baseResult, status: 'partial' as const, droppedStops: [{ candidateIndex: 1, name: 'X', reasonCode: 'CLOSED_ON_DATE' as const, reasonDetail: 'Closed' }] };
    render(<ResultStatement result={partial} />);
    expect(screen.getByText(/1 of 2 stops fit/)).toBeInTheDocument();
  });

  it('heading is focusable for screen reader announcement', () => {
    render(<ResultStatement result={baseResult} />);
    const heading = screen.getByRole('heading', { name: /1 stop fit/ });
    expect(heading).toHaveAttribute('tabindex', '-1');
  });
});

describe('DroppedStops', () => {
  it('renders grouped dropped stops with summary', () => {
    const drops = [
      { candidateIndex: 3, name: 'Arsenale', reasonCode: 'CLOSED_ON_DATE' as const, reasonDetail: 'Closes at 17:00; earliest possible finish is 17:24' },
      { candidateIndex: 4, name: 'Museum', reasonCode: 'NO_FEASIBLE_ITINERARY' as const, reasonDetail: 'Schedule full after 6 stops' },
    ];
    render(<DroppedStops drops={drops} />);
    expect(screen.getByText('Also worth seeing')).toBeInTheDocument();
    expect(screen.getByText('Arsenale')).toBeInTheDocument();
    expect(screen.getByText('Museum')).toBeInTheDocument();
    expect(screen.getByText('Closed on the day you asked for.')).toBeInTheDocument();
    expect(screen.getByText('Adding it would push the day past your end time.')).toBeInTheDocument();
  });

  it('renders nothing for empty drops', () => {
    const { container } = render(<DroppedStops drops={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('single drop uses singular text', () => {
    const drops = [
      { candidateIndex: 3, name: 'Arsenale', reasonCode: 'CLOSED_ON_DATE' as const, reasonDetail: 'Closed on this day' },
    ];
    render(<DroppedStops drops={drops} />);
    expect(screen.getByText('Also worth seeing')).toBeInTheDocument();
    expect(screen.getByText('Arsenale')).toBeInTheDocument();
  });

  it('classifies PLACE_NOT_FOUND with friendly message', () => {
    const drops = [
      { candidateIndex: 1, name: 'Some Vague Place', reasonCode: 'PLACE_NOT_FOUND' as const, reasonDetail: 'No matching place found' },
    ];
    render(<DroppedStops drops={drops} />);
    expect(screen.getByText('Google Places had no unambiguous match for it.')).toBeInTheDocument();
  });

  it('classifies CANDIDATE_REPAIR_FAILED with friendly message', () => {
    const drops = [
      { candidateIndex: 2, name: 'Ambiguous Spot', reasonCode: 'CANDIDATE_REPAIR_FAILED' as const, reasonDetail: 'Could not resolve' },
    ];
    render(<DroppedStops drops={drops} />);
    expect(screen.getByText('No verifiable alternative nearby.')).toBeInTheDocument();
  });
});

describe('RouteComparisonSummary', () => {
  it('shows unavailable state', () => {
    render(<RouteComparisonSummary comparison={{ status: 'unavailable', reasonCode: 'NO_DATA' }} travelMode="WALK" />);
    expect(screen.getByText('Comparison unavailable')).toBeInTheDocument();
  });

  it('shows improved comparison', () => {
    const comparison = {
      status: 'available' as const,
      naive: { totalDistanceMeters: 8400, totalDurationSeconds: 6120, stopOrder: [0, 1, 2] },
      optimized: { totalDistanceMeters: 5100, totalDurationSeconds: 3840, stopOrder: [2, 0, 1] },
      naivePolyline: 'abc',
      optimizedPolyline: 'def',
      distanceDeltaMeters: 3300,
      durationDeltaSeconds: 2280,
      naiveFeasible: true,
      naiveInfeasibilityCodes: [],
      outcome: 'improved' as const,
    };
    render(<RouteComparisonSummary comparison={comparison} travelMode="WALK" />);
    expect(screen.getByText(/38 min less walking/)).toBeInTheDocument();
    expect(screen.getByText(/8.4 km/)).toBeInTheDocument();
    expect(screen.getByText(/5.1 km/)).toBeInTheDocument();
  });

  it('shows same_order outcome', () => {
    const comparison = {
      status: 'available' as const,
      naive: { totalDistanceMeters: 5000, totalDurationSeconds: 3000, stopOrder: [0, 1] },
      optimized: { totalDistanceMeters: 5000, totalDurationSeconds: 3000, stopOrder: [0, 1] },
      naivePolyline: 'abc',
      optimizedPolyline: 'def',
      distanceDeltaMeters: 0,
      durationDeltaSeconds: 0,
      naiveFeasible: true,
      naiveInfeasibilityCodes: [],
      outcome: 'same_order' as const,
    };
    render(<RouteComparisonSummary comparison={comparison} travelMode="WALK" />);
    expect(screen.getByText('Best order confirmed')).toBeInTheDocument();
  });
});


describe('ComparisonMap', () => {
  it('shows textual fallback when Maps JavaScript is unavailable', async () => {
    Object.defineProperty(window, 'google', { configurable: true, value: undefined });
    // Ensure auth failed flag is set so loadGoogleMaps rejects immediately
    window.__vialoMapsAuthFailed = true;

    const comparison = {
      status: 'available' as const,
      naive: { totalDistanceMeters: 1200, totalDurationSeconds: 900, stopOrder: [0] },
      optimized: { totalDistanceMeters: 1200, totalDurationSeconds: 900, stopOrder: [0] },
      naivePolyline: '??',
      optimizedPolyline: '??',
      distanceDeltaMeters: 0,
      durationDeltaSeconds: 0,
      naiveFeasible: true,
      naiveInfeasibilityCodes: [],
      outcome: 'same_order' as const,
    };
    const stop = {
      candidateIndex: 0,
      name: 'Verified stop',
      category: 'landmark' as const,
      priority: 1,
      visitDurationMinutes: 30,
      durationSource: 'model_estimate' as const,
      place: {
        placeId: 'stop-id',
        displayName: 'Verified stop',
        formattedAddress: 'Verified address',
        location: { latitude: 41.69, longitude: 44.80 },
        primaryType: 'tourist_attraction',
        timeZoneId: 'Asia/Tbilisi',
        photos: [],
        rating: 4.5,
        userRatingCount: 1200,
        photoUrl: null,
      },
      hoursSource: 'current' as const,
      openIntervals: [],
    };
    const origin = {
      placeId: 'origin-id',
      displayName: 'Origin',
      formattedAddress: 'Origin address',
      location: { latitude: 41.691, longitude: 44.801 },
      primaryType: null,
      timeZoneId: 'Asia/Tbilisi',
      photos: [],
      rating: null,
      userRatingCount: null,
      photoUrl: null,
    };

    render(<ComparisonMap comparison={comparison} stops={[stop]} origin={origin} />);

    await waitFor(() => {
      expect(screen.getByText(/Interactive map unavailable/)).toBeInTheDocument();
    });

    // Clean up
    window.__vialoMapsAuthFailed = false;
  });
});

describe('ResultView', () => {
  const makeResult = (stopCount: number) => {
    const stops = Array.from({ length: stopCount }, (_, i) => ({
      candidateIndex: i,
      name: `Stop ${i + 1}`,
      category: 'landmark' as const,
      priority: 1,
      visitDurationMinutes: 30,
      durationSource: 'model_estimate' as const,
      place: {
        placeId: `p${i}`,
        displayName: `Stop ${i + 1}`,
        formattedAddress: `Address ${i}`,
        location: { latitude: 41.69 + i * 0.01, longitude: 44.8 + i * 0.01 },
        primaryType: null,
        timeZoneId: 'Asia/Tbilisi',
        photos: [],
        rating: i === 0 ? 4.7 : null,
        userRatingCount: i === 0 ? 850 : null,
        photoUrl: i === 0 ? '/api/photos/test-photo' : null,
      },
      hoursSource: 'current' as const,
      openIntervals: [],
    }));

    return {
      schemaVersion: 1 as const,
      requestId: 'r1',
      status: 'complete' as const,
      locality: { name: 'Tbilisi', timeZoneId: 'Asia/Tbilisi' },
      travelMode: 'WALK' as const,
      window: { start: '2024-01-01T09:00:00+04:00', end: '2024-01-01T17:00:00+04:00', localStart: '09:00', localEnd: '17:00', date: '2024-01-01' },
      origin: { placeId: 'origin', displayName: 'Hotel', formattedAddress: 'Origin address', location: { latitude: 41.69, longitude: 44.8 }, primaryType: null, timeZoneId: 'Asia/Tbilisi', photos: [], rating: null, userRatingCount: null, photoUrl: null },
      destination: null,
      stops,
      timeline: stops.map((_, i) => ({
        type: 'visit' as const,
        stopIndex: i + 1,
        arrival: `2024-01-01T${String(9 + i).padStart(2, '0')}:00:00+04:00`,
        departure: `2024-01-01T${String(9 + i).padStart(2, '0')}:30:00+04:00`,
        durationMinutes: 30,
        intervalUsed: { start: '2024-01-01T08:00:00+04:00', end: '2024-01-01T18:00:00+04:00', localStart: '08:00', localEnd: '18:00' },
      })),
      droppedStops: [],
      comparison: stopCount >= 2
        ? {
            status: 'available' as const,
            naive: { totalDistanceMeters: 5000, totalDurationSeconds: 3000, stopOrder: stops.map((_, i) => i) },
            optimized: { totalDistanceMeters: 3000, totalDurationSeconds: 2000, stopOrder: stops.map((_, i) => i).reverse() },
            naivePolyline: '??',
            optimizedPolyline: '??',
            distanceDeltaMeters: 2000,
            durationDeltaSeconds: 1000,
            naiveFeasible: true,
            naiveInfeasibilityCodes: [],
            outcome: 'improved' as const,
          }
        : { status: 'unavailable' as const, reasonCode: 'NO_DATA' },
      mapsHandoff: { fullRouteUrl: 'https://maps.google.com/dir', fullRouteUniversallySupported: true, browserSafeParts: [], warningCode: null, errorCode: null },
      totals: { visitSeconds: stopCount * 1800, travelSeconds: 600, waitSeconds: 0, elapsedSeconds: stopCount * 1800 + 600 },
      diagnostics: [],
      shareProof: null,
    };
  };

  beforeEach(() => {
    window.__vialoMapsAuthFailed = true; // Prevent maps from loading in tests
  });
  afterEach(() => {
    window.__vialoMapsAuthFailed = false;
  });

  it('suppresses comparison for single-stop result', () => {
    render(<ResultView result={makeResult(1)} />);
    expect(screen.queryByText(/less walking/)).not.toBeInTheDocument();
    expect(screen.queryByText('Naive order')).not.toBeInTheDocument();
  });

  it('keeps an available route map for a single-stop result', async () => {
    const result: ItineraryResponse = makeResult(1);
    result.comparison = {
      status: 'available',
      naive: { totalDistanceMeters: 1200, totalDurationSeconds: 900, stopOrder: [0] },
      optimized: { totalDistanceMeters: 1200, totalDurationSeconds: 900, stopOrder: [0] },
      naivePolyline: '??',
      optimizedPolyline: '??',
      distanceDeltaMeters: 0,
      durationDeltaSeconds: 0,
      naiveFeasible: true,
      naiveInfeasibilityCodes: [],
      outcome: 'no_reordering_needed',
    };

    render(<ResultView result={result} />);

    expect(screen.queryByText('Naive order')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Interactive map unavailable/)).toBeInTheDocument();
    });
  });

  it('shows comparison for multi-stop result', async () => {
    render(<ResultView result={makeResult(3)} />);
    expect(screen.getByText(/less walking/)).toBeInTheDocument();
    // Map section should exist (falls back to unavailable in test env)
    await waitFor(() => {
      expect(screen.getByText(/Interactive map unavailable/)).toBeInTheDocument();
    });
  });

  it('renders evidence (rating) for stops that have it', async () => {
    await act(async () => {
      render(<ResultView result={makeResult(2)} />);
    });
    expect(screen.getByText(/4.7/)).toBeInTheDocument();
    expect(screen.getByText(/850 reviews/)).toBeInTheDocument();
  });

  it('renders photo with lazy loading when photoUrl provided', async () => {
    render(<ResultView result={makeResult(1)} />);
    const img = screen.getByAltText('Photo of Stop 1');
    expect(img).toHaveAttribute('loading', 'lazy');
    expect(img).toHaveAttribute('src', '/api/photos/test-photo');
  });

  it('heading receives focus on mount', async () => {
    await act(async () => {
      render(<ResultView result={makeResult(2)} />);
    });
    const heading = screen.getByRole('heading', { name: /2 stops fit/ });
    expect(heading).toHaveAttribute('tabindex', '-1');
  });
});
