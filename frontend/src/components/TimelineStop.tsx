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
  const unverifiedHours = stop?.hoursSource === 'unverified';
  const hoursAnnotation = unverifiedHours ? 'Hours not available · schedule unconstrained' : null;

  // Evidence: rating and review count
  const rating = stop?.place.rating ?? null;
  const reviewCount = stop?.place.userRatingCount ?? null;
  const photoUrl = stop?.place.photoUrl ?? null;
  const photoAttribution = stop?.place.photos?.[0]?.authorAttributions?.[0] ?? null;

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

        {/* Evidence: rating + review count */}
        {rating !== null && (
          <span className="stop-evidence">
            <span className="stop-rating" aria-label={`Rating ${rating.toFixed(1)} out of 5`}>
              ★ {rating.toFixed(1)}
            </span>
            {reviewCount !== null && reviewCount > 0 && (
              <span className="stop-reviews">({reviewCount.toLocaleString()} reviews)</span>
            )}
          </span>
        )}

        {openAnnotation && !unverifiedHours && (
          <span className="stop-annotation">
            <span aria-hidden="true">🕐</span> {openAnnotation}
          </span>
        )}
        {hoursAnnotation && (
          <span className="stop-annotation stop-annotation-unverified">
            <span aria-hidden="true">🕐</span> {hoursAnnotation}
          </span>
        )}
        {address && <span className="stop-address">{address}</span>}

        {/* Place photo with attribution — uses CSS to hide broken images */}
        {photoUrl && (
          <div className="stop-photo-wrap">
            <img
              src={photoUrl}
              alt={`Photo of ${name}`}
              className="stop-photo"
              loading="lazy"
              decoding="async"
              onError={(e) => {
                // Hide the broken image entirely via inline style
                (e.currentTarget as HTMLImageElement).style.display = 'none';
              }}
            />
            {photoAttribution && (
              <a
                href={photoAttribution.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="photo-attribution"
              >
                Photo: {photoAttribution.displayName}
              </a>
            )}
          </div>
        )}

        {/* Fallback photo credit without image */}
        {!photoUrl && stop?.place.photos?.[0]?.authorAttributions?.[0] && (
          <div className="stop-photo-credit">
            <a
              href={stop.place.photos[0].authorAttributions[0].uri}
              target="_blank"
              rel="noopener noreferrer"
              className="photo-attribution"
            >
              Photo: {stop.place.photos[0].authorAttributions[0].displayName}
            </a>
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
  overflow-wrap: anywhere;
  min-width: 0;
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

.stop-evidence {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 13px;
  color: var(--color-ink-muted);
}

.stop-rating {
  color: var(--color-accent-sun);
  font-weight: 600;
}

.stop-reviews {
  font-size: 12px;
}

.stop-annotation {
  font-size: 12px;
  color: var(--color-warning);
  font-weight: 500;
}

.stop-annotation-unverified {
  color: var(--color-ink-muted);
  font-style: italic;
}

.stop-address {
  font-size: 12px;
  color: var(--color-ink-muted);
}

.stop-photo-wrap {
  margin-top: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.stop-photo {
  width: 100%;
  max-width: 200px;
  height: auto;
  max-height: 120px;
  object-fit: cover;
  border-radius: var(--radius-input);
  border: 1px solid var(--color-border);
}

.stop-photo-credit {
  margin-top: var(--space-1);
}

.photo-attribution {
  font-size: 12px;
  color: var(--color-ink-muted);
  min-height: 12px;
  line-height: 16px;
}
`;
