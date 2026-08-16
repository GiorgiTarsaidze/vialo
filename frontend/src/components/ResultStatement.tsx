import type { ItineraryResponse } from '../lib/types';
import { formatLocalTime, travelModeLabel } from '../lib/format';

interface ResultStatementProps {
  result: ItineraryResponse;
  headingRef?: React.RefObject<HTMLElement | null>;
}

export default function ResultStatement({ result, headingRef }: ResultStatementProps) {
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
      <h1
        id="result-heading"
        className="result-headline"
        tabIndex={-1}
        ref={headingRef as React.RefObject<HTMLHeadingElement>}
      >
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
  margin-bottom: 0;
}

.result-headline {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 34px;
  font-weight: 500;
  color: var(--color-ink);
  outline: none;
}

.result-headline:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
  border-radius: 4px;
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
