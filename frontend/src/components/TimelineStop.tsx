import type { VisitEntry, GroundedStop } from '../lib/types';
import { formatTime } from '../lib/format';

interface TimelineStopProps {
  entry: VisitEntry;
  stop: GroundedStop | undefined;
  sequence: number;
}

export default function TimelineStopRow({ entry, stop, sequence }: TimelineStopProps) {
  const arrivalTime = formatTime(entry.arrival);
  const departureTime = formatTime(entry.departure);
  const durationLabel = `${entry.durationMinutes} min`;
  const provenanceLabel = stop?.durationSource === 'user' ? 'planned' : 'estimated';
  const name = stop?.name ?? 'Unknown stop';
  const address = stop?.place.formattedAddress ?? '';

  const openingTime = stop?.openIntervals?.[0]?.localStart.slice(0, 5);
  const openAnnotation = openingTime === arrivalTime ? `Opens ${openingTime}` : null;

  return (
    <li className="timeline-stop" aria-label={`Stop ${sequence}: ${name}, arrive ${arrivalTime}, depart ${departureTime}, ${durationLabel}`}>
      <div className="stop-time tabular-nums">
        <span className="stop-arrival">{arrivalTime}</span>
        <span className="stop-departure">{departureTime}</span>
      </div>
      <div className="stop-rail">
        <span className="stop-marker" aria-hidden="true">{String(sequence).padStart(2, '0')}</span>
        <span className="stop-connector" aria-hidden="true" />
      </div>
      <div className="stop-content">
        <span className="stop-name">{name}</span>
        <span className="stop-duration">
          {durationLabel} · <span className="stop-provenance">{provenanceLabel}</span>
        </span>
        {openAnnotation && (
          <span className="stop-annotation">
            <span aria-hidden="true">🕐</span> {openAnnotation}
          </span>
        )}
        {address && <span className="stop-address">{address}</span>}

        {/* Photo with attributions */}
        {stop?.place.photos?.[0] && (
          <div className="stop-photo-credit">
            {stop.place.photos[0].authorAttributions.map((attr, i) => (
              <a
                key={i}
                href={attr.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="photo-attribution"
              >
                Photo: {attr.displayName}
              </a>
            ))}
          </div>
        )}
      </div>
      <style>{styles}</style>
    </li>
  );
}

const styles = `
.timeline-stop {
  display: grid;
  grid-template-columns: 52px 36px 1fr;
  gap: 0;
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--color-border);
  min-height: 44px;
  align-items: start;
}

.stop-time {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
  text-align: right;
  padding-right: var(--space-2);
  padding-top: 2px;
}

.stop-departure {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-ink-muted);
}

.stop-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.stop-marker {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #ffffff;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stop-connector {
  width: 2px;
  flex: 1;
  min-height: 16px;
  background: var(--color-border);
  margin-top: var(--space-1);
}

.stop-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: var(--space-2);
  padding-top: 4px;
}

.stop-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
}

.stop-duration {
  font-size: 13px;
  color: var(--color-ink-muted);
}

.stop-provenance {
  font-style: italic;
}

.stop-annotation {
  font-size: 12px;
  color: var(--color-warning);
  font-weight: 500;
}

.stop-address {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.stop-photo-credit {
  margin-top: var(--space-1);
}

.photo-attribution {
  font-size: 11px;
  color: var(--color-ink-muted);
}
`;
