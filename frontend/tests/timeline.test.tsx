import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ScheduledTimeline from '../src/components/ScheduledTimeline';
import type { TimelineEntry, GroundedStop } from '../src/lib/types';

function makeStops(): GroundedStop[] {
  return [
    {
      candidateIndex: 0,
      name: 'Basilica di San Marco',
      category: 'historic_religious_site',
      priority: 1,
      visitDurationMinutes: 50,
      durationSource: 'model_estimate',
      place: {
        placeId: 'p1',
        displayName: 'Basilica di San Marco',
        formattedAddress: 'Piazza San Marco, Venice',
        location: { latitude: 45.434, longitude: 12.339 },
        primaryType: 'church',
        timeZoneId: 'Europe/Rome',
        photos: [],
      },
      hoursSource: 'current',
      openIntervals: [{ start: '2024-01-01T08:30:00Z', end: '2024-01-01T16:30:00Z', localStart: '08:40', localEnd: '17:30' }],
    },
    {
      candidateIndex: 1,
      name: 'Palazzo Ducale',
      category: 'museum_gallery',
      priority: 1,
      visitDurationMinutes: 70,
      durationSource: 'user',
      place: {
        placeId: 'p2',
        displayName: 'Palazzo Ducale',
        formattedAddress: 'Piazza San Marco, 1, Venice',
        location: { latitude: 45.433, longitude: 12.340 },
        primaryType: 'museum',
        timeZoneId: 'Europe/Rome',
        photos: [],
      },
      hoursSource: 'current',
      openIntervals: [],
    },
  ];
}

function makeTimeline(): TimelineEntry[] {
  return [
    {
      type: 'visit',
      stopIndex: 1,
      arrival: '2024-01-01T08:40:00Z',
      departure: '2024-01-01T09:30:00Z',
      durationMinutes: 50,
      intervalUsed: { start: '2024-01-01T08:30:00Z', end: '2024-01-01T16:30:00Z', localStart: '09:30', localEnd: '17:30' },
    },
    {
      type: 'travel',
      fromIndex: 0,
      toIndex: 1,
      mode: 'WALK',
      durationSeconds: 360,
      distanceMeters: 400,
      departure: '2024-01-01T09:30:00Z',
      arrival: '2024-01-01T09:36:00Z',
    },
    {
      type: 'wait',
      stopIndex: 2,
      durationSeconds: 840,
      waitStart: '2024-01-01T09:36:00Z',
      waitEnd: '2024-01-01T09:50:00Z',
      reason: 'Opens 11:20',
    },
    {
      type: 'visit',
      stopIndex: 2,
      arrival: '2024-01-01T09:50:00Z',
      departure: '2024-01-01T11:00:00Z',
      durationMinutes: 70,
      intervalUsed: { start: '2024-01-01T09:50:00Z', end: '2024-01-01T17:00:00Z', localStart: '10:50', localEnd: '18:00' },
    },
  ];
}

describe('ScheduledTimeline', () => {
  it('renders all timeline entries', () => {
    render(<ScheduledTimeline timeline={makeTimeline()} stops={makeStops()} travelMode="WALK" />);
    expect(screen.getByText('Your schedule')).toBeInTheDocument();
    expect(screen.getByText('Basilica di San Marco')).toBeInTheDocument();
    expect(screen.getByText('Palazzo Ducale')).toBeInTheDocument();
  });

  it('shows travel leg', () => {
    render(<ScheduledTimeline timeline={makeTimeline()} stops={makeStops()} travelMode="WALK" />);
    expect(screen.getByText(/Walk 6 min · 400 m/)).toBeInTheDocument();
  });

  it('shows wait entry with reason', () => {
    render(<ScheduledTimeline timeline={makeTimeline()} stops={makeStops()} travelMode="WALK" />);
    expect(screen.getByText(/Wait 14 min/)).toBeInTheDocument();
    expect(screen.getByText('Opens 11:20')).toBeInTheDocument();
  });

  it('shows duration provenance', () => {
    render(<ScheduledTimeline timeline={makeTimeline()} stops={makeStops()} travelMode="WALK" />);
    expect(screen.getByText('estimated')).toBeInTheDocument();
    expect(screen.getByText('planned')).toBeInTheDocument();
  });

  it('shows opening annotation for first stop', () => {
    render(<ScheduledTimeline timeline={makeTimeline()} stops={makeStops()} travelMode="WALK" />);
    expect(screen.getByText(/Opens 08:40/)).toBeInTheDocument();
  });

  it('returns null for empty timeline', () => {
    const { container } = render(<ScheduledTimeline timeline={[]} stops={[]} travelMode="WALK" />);
    expect(container.firstChild).toBeNull();
  });
});
