import type { TravelEntry, TravelMode } from '../lib/types';
import { formatTime, formatDuration, formatDistance, travelLegLabel } from '../lib/format';

interface TimelineTravelProps {
  entry: TravelEntry;
  travelMode: TravelMode;
}

export default function TimelineTravelRow({ entry, travelMode }: TimelineTravelProps) {
  const departureTime = formatTime(entry.departure);
  const duration = formatDuration(entry.durationSeconds);
  const distance = formatDistance(entry.distanceMeters);
  const mode = travelLegLabel(travelMode);

  return (
    <li
      className="timeline-travel"
      aria-label={`${mode} ${duration}, ${distance}`}
    >
      <div className="travel-time tabular-nums">
        <span className="travel-departure">{departureTime}</span>
      </div>
      <div className="travel-rail">
        <span className="travel-line" aria-hidden="true" />
      </div>
      <div className="travel-content">
        <span className="travel-label">
          {mode} {duration} · {distance}
        </span>
      </div>
      <style>{styles}</style>
    </li>
  );
}

const styles = `
.timeline-travel {
  display: grid;
  grid-template-columns: 52px 36px 1fr;
  gap: 0;
  padding: var(--space-2) 0;
  min-height: 44px;
  align-items: center;
}

.travel-time {
  font-size: 13px;
  color: var(--color-ink-muted);
  text-align: right;
  padding-right: var(--space-2);
}

.travel-rail {
  display: flex;
  justify-content: center;
}

.travel-line {
  width: 2px;
  height: 24px;
  background: var(--color-border);
  border-radius: 1px;
}

.travel-content {
  padding-left: var(--space-2);
}

.travel-label {
  font-size: 13px;
  color: var(--color-ink-muted);
  font-weight: 500;
}
`;
