import { useEffect, useRef } from 'react';
import type { ItineraryResponse } from '../lib/types';
import ResultStatement from './ResultStatement';
import RouteComparisonSummary from './RouteComparisonSummary';
import ComparisonMap from './ComparisonMap';
import ScheduledTimeline from './ScheduledTimeline';
import DroppedStops from './DroppedStops';
import ResultActions from './ResultActions';
import CityStories from './CityStories';

interface ResultViewProps {
  result: ItineraryResponse;
  onNewDay?: () => void;
  readOnly?: boolean;
  shareId?: string;
  onShareDeleted?: () => void;
}

export default function ResultView({ result, readOnly, shareId, onShareDeleted }: ResultViewProps) {
  const headingRef = useRef<HTMLElement>(null);

  // Focus result heading on mount for screen reader announcement
  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  // Suppress full comparison when fewer than 2 retained stops
  const showComparison = result.stops.length >= 2 && result.comparison.status === 'available';

  // Show map when any geometry is available (even 1 stop)
  const hasGeometry =
    result.comparison.status === 'available' &&
    (result.comparison.naivePolyline || result.comparison.optimizedPolyline);

  return (
    <section className="result-view" aria-labelledby="result-heading" aria-label="Itinerary result">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        Itinerary ready: {result.stops.length} stops scheduled.
      </div>

      <div className="result-surface">
        {/* Statement always first */}
        <ResultStatement result={result} headingRef={headingRef} />

        {/* Mobile order: statement -> comparison -> timeline -> map -> diagnostics -> actions */}
        {/* Desktop >=1024: timeline 55% left, map 45% right in one grid */}

        {showComparison && (
          <RouteComparisonSummary comparison={result.comparison} travelMode={result.travelMode} />
        )}

        <div className="result-layout">
          <div className="result-layout__timeline">
            <ScheduledTimeline
              timeline={result.timeline}
              stops={result.stops}
              travelMode={result.travelMode}
            />
          </div>

          {hasGeometry && (
            <div className="result-layout__map" aria-label="Route map">
              <ComparisonMap
                comparison={result.comparison}
                stops={result.stops}
                origin={result.origin}
                destination={result.destination}
              />
            </div>
          )}
        </div>

        {/* Dropped stops — grouped diagnostics */}
        {result.droppedStops.length > 0 && (
          <DroppedStops drops={result.droppedStops} />
        )}

        {/* City stories */}
        <CityStories cityName={result.locality.name} />

        {/* Actions */}
        <ResultActions
          result={result}
          readOnly={readOnly}
          shareId={shareId}
          onShareDeleted={onShareDeleted}
        />

        {/* Publish as journal story */}
        {!readOnly && (
          <a
            href="/journal/new"
            className="result-publish-link"
            onClick={(e) => {
              e.preventDefault();
              sessionStorage.setItem('vialo.journal.draft_itinerary', JSON.stringify(result));
              window.location.href = '/journal/new';
            }}
          >
            Publish this day as a story
          </a>
        )}
      </div>

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.result-view {
  padding-top: var(--space-5);
  overflow-wrap: anywhere;
}

.result-surface {
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

@media (min-width: 768px) {
  .result-surface {
    padding: var(--space-6);
    gap: var(--space-6);
  }
}

@media (min-width: 1024px) {
  .result-surface {
    padding: var(--space-7);
  }
}

.result-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  min-width: 0;
}

@media (min-width: 1024px) {
  .result-layout {
    display: grid;
    grid-template-columns: 55fr 45fr;
    gap: var(--space-6);
    align-items: start;
  }
}

.result-layout__timeline {
  min-width: 0;
  overflow: hidden;
}

.result-layout__map {
  min-width: 0;
  overflow: hidden;
}

@media (min-width: 1024px) {
  .result-layout__map {
    position: sticky;
    top: var(--space-5);
  }
}

.result-publish-link {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 52px;
  padding: var(--space-3) var(--space-5);
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-input);
  text-decoration: none;
  text-align: center;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
  max-width: 480px;
  transition: background var(--duration-fast) ease;
}

.result-publish-link:hover {
  background: var(--color-surface);
  color: var(--color-ink);
}
`;
