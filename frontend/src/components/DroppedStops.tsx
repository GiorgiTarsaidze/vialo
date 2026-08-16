import { useState } from 'react';
import type { DroppedStop, DiagnosticCode } from '../lib/types';

interface DroppedStopsProps {
  drops: DroppedStop[];
}

type DropGroup = 'hours' | 'schedule' | 'place';

function classifyDrop(code: DiagnosticCode): DropGroup {
  switch (code) {
    case 'CLOSED_ON_DATE':
    case 'HOURS_UNAVAILABLE':
      return 'hours';
    case 'NO_FEASIBLE_ITINERARY':
    case 'NO_REACHABLE_STOPS':
      return 'schedule';
    case 'PLACE_NOT_FOUND':
    case 'CANDIDATE_REPAIR_FAILED':
      return 'place';
    default:
      return 'schedule';
  }
}

const GROUP_LABELS: Record<DropGroup, string> = {
  hours: 'Closed or hours unknown',
  schedule: "Didn't fit the schedule",
  place: 'Choose a specific place',
};

export default function DroppedStops({ drops }: DroppedStopsProps) {
  const [expanded, setExpanded] = useState(false);

  if (drops.length === 0) return null;

  // Group drops
  const groups = new Map<DropGroup, DroppedStop[]>();
  for (const drop of drops) {
    const group = classifyDrop(drop.reasonCode);
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group)!.push(drop);
  }

  // Compact summary: group counts
  const groupSummaryParts: string[] = [];
  for (const [group, groupDrops] of groups) {
    groupSummaryParts.push(`${groupDrops.length} ${GROUP_LABELS[group].toLowerCase()}`);
  }
  const summaryText = drops.length === 1
    ? `1 stop couldn't fit`
    : `${drops.length} stops couldn't fit`;

  return (
    <section className="dropped-stops" aria-labelledby="dropped-heading">
      <div className="dropped-header">
        <h3 id="dropped-heading" className="dropped-title">{summaryText}</h3>
        <span className="dropped-summary-counts">
          {groupSummaryParts.join(' · ')}
        </span>
        {drops.length > 2 && (
          <button
            className="dropped-toggle"
            type="button"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls="dropped-details"
          >
            {expanded ? 'Show less' : 'Show details'}
          </button>
        )}
      </div>

      <div
        id="dropped-details"
        role="region"
        aria-label="Dropped stop details"
        className={drops.length <= 2 || expanded ? 'dropped-details--open' : 'dropped-details--summary'}
      >
        {Array.from(groups.entries()).map(([group, groupDrops]) => (
          <div key={group} className="dropped-group">
            <span className="dropped-group-label">{GROUP_LABELS[group]}</span>
            <ul className="dropped-list" aria-label={`${GROUP_LABELS[group]} stops`}>
              {groupDrops.map((drop) => (
                <li key={drop.candidateIndex} className="dropped-item">
                  <span className="dropped-name">{drop.name}</span>
                  <span className="dropped-reason">{drop.reasonDetail}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <style>{styles}</style>
    </section>
  );
}

const styles = `
.dropped-stops {
  padding: var(--space-4);
  background: var(--color-naive-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.dropped-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.dropped-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-naive);
  margin: 0;
}

.dropped-summary-counts {
  font-size: 13px;
  color: var(--color-ink-muted);
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

.dropped-details--summary .dropped-group:first-child {
  display: block;
}

.dropped-details--summary .dropped-group:not(:first-child) {
  display: none;
}

.dropped-details--open {
  margin-top: var(--space-3);
}

.dropped-details--summary {
  margin-top: var(--space-3);
}

.dropped-group {
  margin-bottom: var(--space-3);
}

.dropped-group:last-child {
  margin-bottom: 0;
}

.dropped-group-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.02em;
  display: block;
  margin-bottom: var(--space-2);
}

.dropped-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.dropped-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
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
