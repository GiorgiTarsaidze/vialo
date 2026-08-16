import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import InputHero from '../src/components/InputHero';
import LoadingPipeline from '../src/components/LoadingPipeline';
import ResultStatement from '../src/components/ResultStatement';
import DroppedStops from '../src/components/DroppedStops';
import RouteComparisonSummary from '../src/components/RouteComparisonSummary';
import ComparisonMap from '../src/components/ComparisonMap';

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

  it('fills input on example click without submitting', async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    wrap(<InputHero onSubmit={onSubmit} />);
    const example = screen.getByRole('button', { name: /Venice morning/ });
    await user.click(example);
    const textarea = screen.getByRole('textbox', { name: /Describe your day/ }) as HTMLTextAreaElement;
    expect(textarea.value).toContain('Venice');
    expect(onSubmit).not.toHaveBeenCalled();
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
    expect(screen.getByRole('alert')).toHaveTextContent('Retry available in 2m 0s');
    expect(screen.getByRole('button', { name: /Build my day/ })).toBeDisabled();
  });
});

describe('LoadingPipeline', () => {
  it('shows all stages', () => {
    render(<LoadingPipeline />);
    expect(screen.getByText('Finding places')).toBeInTheDocument();
    expect(screen.getByText('Checking opening hours')).toBeInTheDocument();
    expect(screen.getByText('Measuring travel')).toBeInTheDocument();
    expect(screen.getByText('Solving the order')).toBeInTheDocument();
    expect(screen.getByText('Drawing the routes')).toBeInTheDocument();
  });

  it('shows slow message after timeout', () => {
    vi.useFakeTimers();
    render(<LoadingPipeline />);
    expect(screen.queryByText(/taking longer/)).not.toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(8001); });
    expect(screen.getByText(/taking longer than usual/)).toBeInTheDocument();
    vi.useRealTimers();
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
    origin: { placeId: 'p1', displayName: 'Hotel', formattedAddress: 'Via X', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [] },
    stops: [
      { candidateIndex: 0, name: 'Place A', category: 'landmark' as const, priority: 1, visitDurationMinutes: 30, durationSource: 'model_estimate' as const, place: { placeId: 'pa', displayName: 'Place A', formattedAddress: 'Addr', location: { latitude: 45.4, longitude: 12.3 }, primaryType: null, timeZoneId: 'Europe/Rome', photos: [] }, hoursSource: 'current' as const, openIntervals: [] },
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
});

describe('DroppedStops', () => {
  it('renders dropped stops with reasons', () => {
    const drops = [
      { candidateIndex: 3, name: 'Arsenale', reasonCode: 'CLOSED_ON_DATE' as const, reasonDetail: 'Closes at 17:00; earliest possible finish is 17:24' },
    ];
    render(<DroppedStops drops={drops} />);
    expect(screen.getByText("Couldn't fit")).toBeInTheDocument();
    expect(screen.getByText('Arsenale')).toBeInTheDocument();
    expect(screen.getByText(/Closes at 17:00/)).toBeInTheDocument();
  });

  it('renders nothing for empty drops', () => {
    const { container } = render(<DroppedStops drops={[]} />);
    expect(container.firstChild).toBeNull();
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
  it('keeps a visible textual fallback when Maps JavaScript is unavailable', async () => {
    Object.defineProperty(window, 'google', { configurable: true, value: undefined });
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
    };

    render(<ComparisonMap comparison={comparison} stops={[stop]} origin={origin} />);

    expect(screen.getByRole('img', { name: /single optimized route/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Interactive map unavailable/)).toBeInTheDocument();
    });
  });
});
