import type { ItineraryResponse } from '../lib/types';
import ResultStatement from './ResultStatement';
import RouteComparisonSummary from './RouteComparisonSummary';
import ComparisonMap from './ComparisonMap';
import ScheduledTimeline from './ScheduledTimeline';
import DroppedStops from './DroppedStops';
import ResultActions from './ResultActions';

interface ResultViewProps {
  result: ItineraryResponse;
  onNewDay?: () => void;
  readOnly?: boolean;
  shareId?: string;
  onShareDeleted?: () => void;
}

export default function ResultView({ result, readOnly, shareId, onShareDeleted }: ResultViewProps) {
  return (
    <section className="result-view" aria-labelledby="result-heading">
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        Itinerary ready: {result.stops.length} stops scheduled.
      </div>

      <ResultStatement result={result} />

      <RouteComparisonSummary comparison={result.comparison} travelMode={result.travelMode} />

      <div className="result-grid">
        <div className="result-map">
          <ComparisonMap
            comparison={result.comparison}
            stops={result.stops}
            origin={result.origin}
          />
        </div>
        <div className="result-timeline">
          <ScheduledTimeline
            timeline={result.timeline}
            stops={result.stops}
            travelMode={result.travelMode}
          />
        </div>
      </div>

      {result.droppedStops.length > 0 && (
        <DroppedStops drops={result.droppedStops} />
      )}

      <ResultActions
        result={result}
        readOnly={readOnly}
        shareId={shareId}
        onShareDeleted={onShareDeleted}
      />

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.result-view {
  padding-top: var(--space-5);
}

.result-grid {
  display: grid;
  grid-template-areas:
    "map"
    "timeline";
  gap: var(--space-6);
}

.result-map {
  grid-area: map;
  min-width: 0;
}

.result-timeline {
  grid-area: timeline;
  min-width: 0;
}

@media (min-width: 1024px) {
  .result-grid {
    grid-template-columns: minmax(0, 55fr) minmax(360px, 45fr);
    grid-template-areas: "timeline map";
    align-items: start;
  }

  .result-map {
    position: sticky;
    top: var(--space-4);
  }
}
`;
