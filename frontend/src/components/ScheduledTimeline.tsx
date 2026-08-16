import type { TimelineEntry, GroundedStop, TravelMode } from '../lib/types';
import TimelineStopRow from './TimelineStop';
import TimelineTravelRow from './TimelineTravel';
import TimelineWaitRow from './TimelineWait';

interface ScheduledTimelineProps {
  timeline: TimelineEntry[];
  stops: GroundedStop[];
  travelMode: TravelMode;
}

export default function ScheduledTimeline({ timeline, stops, travelMode }: ScheduledTimelineProps) {
  if (timeline.length === 0) return null;

  // Build an ordered sequence number for each visit
  let visitSeq = 0;

  return (
    <section className="scheduled-timeline" aria-labelledby="timeline-heading">
      <h2 id="timeline-heading" className="timeline-title">Your schedule</h2>
      <ol className="timeline-list" aria-label="Scheduled stops and travel">
        {timeline.map((entry, i) => {
          if (entry.type === 'visit') {
            visitSeq++;
            const stop = stops[entry.stopIndex - 1];
            return (
              <TimelineStopRow
                key={`visit-${i}`}
                entry={entry}
                stop={stop}
                sequence={visitSeq}
              />
            );
          }
          if (entry.type === 'travel') {
            return (
              <TimelineTravelRow
                key={`travel-${i}`}
                entry={entry}
                travelMode={travelMode}
              />
            );
          }
          if (entry.type === 'wait') {
            return (
              <TimelineWaitRow
                key={`wait-${i}`}
                entry={entry}
              />
            );
          }
          return null;
        })}
      </ol>
      <style>{styles}</style>
    </section>
  );
}

const styles = `
.scheduled-timeline {
  margin-top: var(--space-5);
}

.timeline-title {
  font-size: 22px;
  line-height: 28px;
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: var(--space-4);
}

.timeline-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
}
`;
