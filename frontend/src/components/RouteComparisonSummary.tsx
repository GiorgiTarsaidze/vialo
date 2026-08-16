import type { ComparisonResult, TravelMode } from '../lib/types';
import { formatDuration, formatDistance, travelModeLabel } from '../lib/format';

interface RouteComparisonSummaryProps {
  comparison: ComparisonResult;
  travelMode: TravelMode;
}

function getSavingsHeadline(comparison: ComparisonResult, travelMode: TravelMode): string {
  if (comparison.status === 'unavailable') {
    return 'Comparison unavailable';
  }

  const mode = travelModeLabel(travelMode);

  switch (comparison.outcome) {
    case 'same_order':
      return 'Best order confirmed';
    case 'no_reordering_needed':
      return 'One stop · no reordering needed';
    case 'metrics_diverged':
      return 'Schedule-aware order';
    case 'improved': {
      const durationSaved = comparison.durationDeltaSeconds;
      const distSaved = comparison.distanceDeltaMeters;
      if (durationSaved > 0 && durationSaved >= 60) {
        return `${formatDuration(durationSaved)} less ${mode}`;
      }
      if (distSaved > 0) {
        return `${formatDistance(distSaved)} less ${mode}`;
      }
      // Feasibility improvement
      if (!comparison.naiveFeasible) {
        return 'Fits every closing time';
      }
      return `Optimized ${mode} route`;
    }
    default:
      return 'Route comparison';
  }
}

export default function RouteComparisonSummary({ comparison, travelMode }: RouteComparisonSummaryProps) {
  if (comparison.status === 'unavailable') {
    return (
      <div className="comparison-summary comparison-unavailable" role="region" aria-label="Route comparison">
        <p className="comparison-headline">Comparison unavailable</p>
        <p className="comparison-note">Schedule and timeline are still available below.</p>
        <style>{styles}</style>
      </div>
    );
  }

  const mode = travelModeLabel(travelMode);
  const headline = getSavingsHeadline(comparison, travelMode);

  const naiveLabel = `Naive order`;
  const optimizedLabel = `Vialo order`;

  const naiveMetrics = `${formatDistance(comparison.naive.totalDistanceMeters)} · ${formatDuration(comparison.naive.totalDurationSeconds)} ${mode}`;
  const optimizedMetrics = `${formatDistance(comparison.optimized.totalDistanceMeters)} · ${formatDuration(comparison.optimized.totalDurationSeconds)} ${mode}`;

  const naiveFeasibility = comparison.naiveFeasible
    ? `Fits ${travelMode === 'WALK' ? 'schedule' : 'schedule'}`
    : comparison.naiveInfeasibilityCodes.length > 0
      ? 'Misses a closing time'
      : 'Infeasible';

  const optimizedFeasibility = 'Fits schedule';

  return (
    <div className="comparison-summary" role="region" aria-label="Route comparison">
      <h2 className="comparison-headline">{headline}</h2>

      <div className="comparison-routes">
        <div className="route-row route-row--naive">
          <span className="route-stroke route-stroke--naive" aria-hidden="true" />
          <div className="route-info">
            <span className="route-label">{naiveLabel}</span>
            <span className="route-metrics tabular-nums">{naiveMetrics}</span>
            <span className="route-feasibility route-feasibility--naive">{naiveFeasibility}</span>
          </div>
        </div>

        <div className="route-row route-row--optimized">
          <span className="route-stroke route-stroke--optimized" aria-hidden="true" />
          <div className="route-info">
            <span className="route-label">{optimizedLabel}</span>
            <span className="route-metrics tabular-nums">{optimizedMetrics}</span>
            <span className="route-feasibility route-feasibility--optimized">{optimizedFeasibility}</span>
          </div>
        </div>
      </div>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.comparison-summary {
  overflow-wrap: anywhere;
}

.comparison-headline {
  font-size: 22px;
  line-height: 28px;
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: var(--space-3);
}

.comparison-unavailable .comparison-note {
  font-size: 14px;
  color: var(--color-ink-muted);
}

.comparison-routes {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
}

@media (min-width: 640px) {
  .comparison-routes {
    flex-direction: row;
    gap: var(--space-6);
  }
}

.route-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.route-stroke {
  width: 24px;
  height: 3px;
  margin-top: 10px;
  flex-shrink: 0;
  border-radius: 2px;
}

.route-stroke--naive {
  background: var(--color-naive);
  opacity: 0.62;
  background-image: repeating-linear-gradient(
    90deg,
    var(--color-naive) 0px,
    var(--color-naive) 8px,
    transparent 8px,
    transparent 14px
  );
  background-color: transparent;
}

.route-stroke--optimized {
  background: var(--color-optimized);
  height: 4px;
  margin-top: 9px;
}

.route-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.route-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-muted);
}

.route-metrics {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-ink);
}

.route-feasibility {
  font-size: 12px;
  font-weight: 500;
}

.route-feasibility--naive {
  color: var(--color-naive);
}

.route-feasibility--optimized {
  color: var(--color-success);
}
`;
