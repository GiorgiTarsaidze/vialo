import type { DroppedStop } from '../lib/types';

interface DroppedStopsProps {
  drops: DroppedStop[];
}

export default function DroppedStops({ drops }: DroppedStopsProps) {
  if (drops.length === 0) return null;

  return (
    <section className="dropped-stops" aria-labelledby="dropped-heading">
      <h3 id="dropped-heading" className="dropped-title">Couldn't fit</h3>
      <ul className="dropped-list" aria-label="Stops that could not be scheduled">
        {drops.map((drop) => (
          <li key={drop.candidateIndex} className="dropped-item">
            <span className="dropped-name">{drop.name}</span>
            <span className="dropped-reason">{drop.reasonDetail}</span>
          </li>
        ))}
      </ul>
      <style>{styles}</style>
    </section>
  );
}

const styles = `
.dropped-stops {
  margin-top: var(--space-6);
  padding: var(--space-4);
  background: var(--color-naive-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.dropped-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-naive);
  margin-bottom: var(--space-3);
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
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
}

.dropped-reason {
  font-size: 13px;
  color: var(--color-ink-muted);
}
`;
