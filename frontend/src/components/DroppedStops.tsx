import { useState } from 'react';
import type { DroppedStop, DiagnosticCode } from '../lib/types';

interface DroppedStopsProps {
  drops: DroppedStop[];
}

function friendlyReason(code: DiagnosticCode, reasonDetail: string): string {
  switch (code) {
    case 'NO_FEASIBLE_ITINERARY':
      // Deliberately does not name a cause. The solver knows this stop could not
      // be fitted alongside the others, not which constraint did it: the window,
      // an opening time, or the travel between them. Claiming "past your end
      // time" was wrong often enough to be misleading, including on days that
      // finished hours before their window closed.
      return 'It could not be fitted around the other stops and their opening times.';
    case 'CLOSED_ON_DATE':
      return 'Closed on the day you asked for.';
    case 'HOURS_UNAVAILABLE':
      return 'No published opening hours to schedule against.';
    case 'PLACE_NOT_FOUND':
      return 'Google Places had no unambiguous match for it.';
    case 'OUTSIDE_LOCALITY':
      return 'Outside the area you asked about.';
    case 'DUPLICATE_PLACE':
      return 'Same place as another stop.';
    case 'CANDIDATE_REPAIR_FAILED':
      return 'No verifiable alternative nearby.';
    default:
      return reasonDetail;
  }
}

export default function DroppedStops({ drops }: DroppedStopsProps) {
  const [expanded, setExpanded] = useState(false);

  if (drops.length === 0) return null;

  const showAll = drops.length <= 2 || expanded;

  return (
    <section className="dropped-stops" aria-labelledby="dropped-heading">
      <div className="dropped-header">
        <h3 id="dropped-heading" className="dropped-title">Also worth seeing</h3>
        <p className="dropped-subtitle">Great stops that did not fit this schedule.</p>
        {drops.length > 2 && (
          <button
            className="dropped-toggle"
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls="dropped-details"
          >
            {expanded ? 'Show less' : `Show all ${drops.length}`}
          </button>
        )}
      </div>

      <ul
        id="dropped-details"
        role="list"
        aria-label="Stops that did not fit"
        className="dropped-list"
      >
        {(showAll ? drops : drops.slice(0, 2)).map((drop) => (
          <li key={drop.candidateIndex} className="dropped-item">
            <span className="dropped-name">{drop.name}</span>
            <span className="dropped-reason">{friendlyReason(drop.reasonCode, drop.reasonDetail)}</span>
          </li>
        ))}
      </ul>
      <style>{styles}</style>
    </section>
  );
}

const styles = `
.dropped-stops {
  padding: var(--space-4);
  background: var(--color-accent-lilac);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.dropped-header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.dropped-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

.dropped-subtitle {
  font-size: 13px;
  color: var(--color-ink-muted);
  flex-basis: 100%;
  margin: 0;
}

.dropped-toggle {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  min-height: 44px;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-input);
}

.dropped-toggle:hover {
  background: var(--color-primary-soft);
}

.dropped-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.dropped-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.dropped-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-ink);
}

.dropped-reason {
  font-size: 13px;
  color: var(--color-ink-muted);
  overflow-wrap: anywhere;
}
`;
