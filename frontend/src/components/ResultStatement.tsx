import type { ItineraryResponse } from '../lib/types';
import { formatLocalTime, travelModeLabel } from '../lib/format';

interface ResultStatementProps {
  result: ItineraryResponse;
}

export default function ResultStatement({ result }: ResultStatementProps) {
  const stopCount = result.stops.length;
  const totalRequested = stopCount + result.droppedStops.length;
  const statusText =
    result.status === 'partial'
      ? `${stopCount} of ${totalRequested} stops fit`
      : `${stopCount} stop${stopCount !== 1 ? 's' : ''} fit`;

  const timeRange = `${formatLocalTime(result.window.localStart)}–${formatLocalTime(result.window.localEnd)}`;
  const mode = travelModeLabel(result.travelMode);

  return (
    <header className="result-statement">
      <h1 id="result-heading" className="result-headline">
        {statusText} {timeRange}
      </h1>
      <p className="result-meta">
        {result.locality.name} · {mode}
      </p>
      <style>{styles}</style>
    </header>
  );
}

const styles = `
.result-statement {
  margin-bottom: var(--space-5);
}

.result-headline {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 34px;
  font-weight: 500;
  color: var(--color-ink);
}

.result-meta {
  font-size: 15px;
  color: var(--color-ink-muted);
  margin-top: var(--space-1);
}

@media (min-width: 640px) {
  .result-headline {
    font-size: 38px;
    line-height: 42px;
  }
}
`;
