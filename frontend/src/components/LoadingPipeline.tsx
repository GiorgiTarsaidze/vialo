import { useState, useEffect } from 'react';

const STAGES = [
  'Finding places',
  'Checking opening hours',
  'Measuring travel',
  'Solving the order',
  'Drawing the routes',
];

const SLOW_THRESHOLD_MS = 8000;

export default function LoadingPipeline() {
  const [showSlow, setShowSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setShowSlow(true), SLOW_THRESHOLD_MS);
    return () => clearTimeout(timer);
  }, []);

  return (
    <section className="loading-pipeline" aria-labelledby="loading-heading" aria-live="polite">
      <h2 id="loading-heading" className="loading-headline">
        Building a day that fits
      </h2>

      <ul className="loading-stages" aria-label="Processing stages">
        {STAGES.map((stage) => (
          <li key={stage} className="loading-stage">
            <span className="stage-dot" aria-hidden="true" />
            {stage}
          </li>
        ))}
      </ul>

      {showSlow && (
        <p className="loading-slow" role="status">
          This is taking longer than usual
        </p>
      )}

      {/* Skeleton blocks matching final layout */}
      <div className="loading-skeleton" aria-hidden="true">
        <div className="skeleton-comparison" />
        <div className="skeleton-timeline" />
      </div>

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.loading-pipeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-top: var(--space-8);
  max-width: 640px;
  margin: 0 auto;
}

.loading-headline {
  font-family: var(--font-display);
  font-size: 28px;
  line-height: 34px;
  font-weight: 500;
  color: var(--color-ink);
  margin-bottom: var(--space-6);
}

.loading-stages {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  text-align: left;
  margin-bottom: var(--space-6);
}

.loading-stage {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: 15px;
  color: var(--color-ink-muted);
}

.stage-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border-strong);
  flex-shrink: 0;
}

.loading-slow {
  font-size: 14px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-pill);
  margin-bottom: var(--space-6);
}

.loading-skeleton {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.skeleton-comparison {
  height: 120px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

.skeleton-timeline {
  height: 300px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
}

@media (prefers-reduced-motion: no-preference) {
  .skeleton-comparison,
  .skeleton-timeline {
    animation: skeleton-pulse 1.5s ease-in-out infinite;
  }

  @keyframes skeleton-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
}
`;
