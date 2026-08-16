import { useState, useEffect, useRef } from 'react';

const STAGES = [
  { key: 'places', label: 'Finding places' },
  { key: 'hours', label: 'Checking opening hours' },
  { key: 'travel', label: 'Measuring travel times' },
  { key: 'solve', label: 'Solving the optimal order' },
  { key: 'routes', label: 'Building route geometry' },
] as const;

// Conservative milestones (cumulative ms) — indicative only
const STAGE_MILESTONES = [0, 2000, 4500, 7000, 10000];
const SLOW_THRESHOLD_MS = 12000;

export default function LoadingPipeline() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [showSlow, setShowSlow] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    const timers: ReturnType<typeof setTimeout>[] = [];

    // Schedule stage advances at milestones
    for (let i = 1; i < STAGE_MILESTONES.length; i++) {
      const timer = setTimeout(() => {
        if (mountedRef.current) {
          setActiveIndex(i);
        }
      }, STAGE_MILESTONES[i]);
      timers.push(timer);
    }

    // Schedule slow message
    const slowTimer = setTimeout(() => {
      if (mountedRef.current) {
        setShowSlow(true);
      }
    }, SLOW_THRESHOLD_MS);
    timers.push(slowTimer);

    return () => {
      timers.forEach(clearTimeout);
    };
  }, []);

  return (
    <section className="loading-pipeline" aria-labelledby="loading-heading">
      <h2 id="loading-heading" className="loading-headline">
        Building a day that fits
      </h2>

      {/* Stage list */}
      <ol className="pipeline-stages" aria-label="Pipeline stages">
        {STAGES.map((stage, i) => {
          const isComplete = i < activeIndex;
          const isCurrent = i === activeIndex;
          return (
            <li
              key={stage.key}
              className={`pipeline-stage ${isComplete ? 'pipeline-stage--complete' : ''} ${isCurrent ? 'pipeline-stage--current' : ''}`}
              aria-current={isCurrent ? 'step' : undefined}
            >
              <span className="stage-indicator" aria-hidden="true">
                {isComplete ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                    <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : isCurrent ? (
                  <span className="stage-spinner" />
                ) : (
                  <span className="stage-pending" />
                )}
              </span>
              <span className="stage-label">{stage.label}</span>
              {isComplete && <span className="sr-only">(complete)</span>}
              {isCurrent && <span className="sr-only">(in progress)</span>}
            </li>
          );
        })}
      </ol>

      {/* Honesty note — visible to all */}
      <p className="pipeline-honesty">
        Working through the usual pipeline; your result confirms completion.
      </p>

      {/* Live region for screen readers — announces current stage only */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {STAGES[activeIndex]?.label ?? 'Processing'} in progress
      </div>

      {showSlow && (
        <p className="pipeline-slow" role="status">
          Still working — provider checks can take a little longer
        </p>
      )}

      {/* Result-shaped preview */}
      <div className="pipeline-preview" aria-hidden="true">
        {/* Route preview shape */}
        <div className="preview-route">
          <span className="preview-route-label">Route preview</span>
          <svg
            className="preview-route-svg"
            viewBox="0 0 280 60"
            fill="none"
            aria-hidden="true"
          >
            {/* Route path with animated dash */}
            <path
              className="preview-route-path"
              d="M20 45 Q70 10, 140 30 T260 20"
              stroke="var(--color-primary)"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
            />
            {/* Stop nodes */}
            <circle cx="20" cy="45" r="5" fill="var(--color-primary)" />
            <circle cx="100" cy="22" r="4" fill="var(--color-border-strong)" />
            <circle cx="180" cy="32" r="4" fill="var(--color-border-strong)" />
            <circle cx="260" cy="20" r="5" fill="var(--color-primary)" />
          </svg>
        </div>

        {/* Schedule preview shape */}
        <div className="preview-schedule">
          <span className="preview-schedule-label">Schedule preview</span>
          <div className="preview-timeline">
            {[1, 2, 3, 4].map((n) => (
              <div key={n} className="preview-timeline-row">
                <span className="preview-time-block" />
                <span className="preview-rail">
                  <span className="preview-rail-dot" />
                  {n < 4 && <span className="preview-rail-line" />}
                </span>
                <span className="preview-place-block" />
              </div>
            ))}
          </div>
        </div>
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

.pipeline-stages {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  text-align: left;
  margin-bottom: var(--space-4);
  width: 100%;
  max-width: 300px;
}

.pipeline-stage {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink-muted);
  transition: color var(--duration-fast) ease;
}

.pipeline-stage--complete {
  color: var(--color-success);
}

.pipeline-stage--current {
  color: var(--color-ink);
  font-weight: 500;
}

.stage-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.pipeline-stage--complete .stage-indicator {
  color: var(--color-success);
}

.stage-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--color-border);
  border-top-color: var(--color-primary);
  border-radius: 50%;
}

@media (prefers-reduced-motion: no-preference) {
  .stage-spinner {
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }
}

.stage-pending {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border);
}

.stage-label {
  flex: 1;
}

.pipeline-honesty {
  font-size: 12px;
  line-height: 16px;
  color: var(--color-ink-muted);
  margin-bottom: var(--space-5);
  max-width: 300px;
}

.pipeline-slow {
  font-size: 14px;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-pill);
  margin-bottom: var(--space-5);
}

/* Result-shaped preview */
.pipeline-preview {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.preview-route {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.preview-route-label,
.preview-schedule-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-align: left;
}

.preview-route-svg {
  width: 100%;
  height: 60px;
}

@media (prefers-reduced-motion: no-preference) {
  .preview-route-path {
    stroke-dasharray: 8 6;
    animation: route-dash 1.5s linear infinite;
  }

  @keyframes route-dash {
    to { stroke-dashoffset: -28; }
  }
}

.preview-schedule {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-card);
  padding: var(--space-3) var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.preview-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.preview-timeline-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 28px;
}

.preview-time-block {
  width: 40px;
  height: 12px;
  background: var(--color-border);
  border-radius: 4px;
  opacity: 0.6;
}

.preview-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  height: 100%;
  width: 12px;
}

.preview-rail-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-primary-soft);
  border: 2px solid var(--color-primary);
  flex-shrink: 0;
}

.preview-rail-line {
  position: absolute;
  top: 100%;
  width: 2px;
  height: var(--space-3);
  background: var(--color-border);
}

.preview-place-block {
  flex: 1;
  height: 12px;
  background: var(--color-border);
  border-radius: 4px;
  opacity: 0.5;
  max-width: 160px;
}

/* Screen reader only */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
`;
