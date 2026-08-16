import type { WaitEntry } from '../lib/types';
import { formatTime, formatDuration } from '../lib/format';

interface TimelineWaitProps {
  entry: WaitEntry;
}

export default function TimelineWaitRow({ entry }: TimelineWaitProps) {
  const startTime = formatTime(entry.waitStart);
  const duration = formatDuration(entry.durationSeconds);

  return (
    <li
      className="timeline-wait"
      aria-label={`Wait ${duration}: ${entry.reason}`}
    >
      <div className="wait-time tabular-nums">
        <span className="wait-start">{startTime}</span>
      </div>
      <div className="wait-rail">
        <span className="wait-indicator" aria-hidden="true" />
      </div>
      <div className="wait-content">
        <span className="wait-label">Wait {duration}</span>
        <span className="wait-reason">{entry.reason}</span>
      </div>
      <style>{styles}</style>
    </li>
  );
}

const styles = `
.timeline-wait {
  display: grid;
  grid-template-columns: 52px 36px 1fr;
  gap: 0;
  padding: var(--space-2) 0;
  min-height: 44px;
  align-items: center;
}

.wait-time {
  font-size: 13px;
  color: var(--color-ink-muted);
  text-align: right;
  padding-right: var(--space-2);
  font-weight: 500;
}

.wait-rail {
  display: flex;
  justify-content: center;
}

.wait-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid var(--color-warning);
  background: var(--color-accent-sun-soft);
}

.wait-content {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-left: var(--space-2);
  background: var(--color-accent-sun-soft);
  border-radius: 8px;
  padding: var(--space-2) var(--space-3);
}

.wait-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-warning);
}

.wait-reason {
  font-size: 12px;
  color: var(--color-ink-muted);
}
`;
