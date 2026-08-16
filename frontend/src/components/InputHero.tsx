import { useState, useRef, useCallback, useEffect } from 'react';
import type { PlanningError } from '../hooks/use-planning';
import LoadingPipeline from './LoadingPipeline';

const MAX_CHARS = 500;

const EXAMPLES = [
  {
    label: 'Venice morning',
    text: 'Venice, 09:00–14:00, architecture and quiet streets, on foot',
  },
  {
    label: 'Napoli essentials',
    text: 'Naples, 10:00–18:00, the highlights plus great pizza for lunch, walking',
  },
  {
    label: 'Lisbon viewpoints',
    text: 'Lisbon, 08:30–16:00, miradouros and tiles, walking',
  },
];

function formatRetryTime(milliseconds: number): string {
  const totalSeconds = Math.max(1, Math.ceil(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

interface InputHeroProps {
  onSubmit: (prompt: string) => void;
  loading?: boolean;
  error?: PlanningError | null;
}

export default function InputHero({ onSubmit, loading, error }: InputHeroProps) {
  const [value, setValue] = useState('');
  const [retryRemainingMs, setRetryRemainingMs] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const duration = error?.retryAfterMs ?? 0;
    setRetryRemainingMs(duration);
    if (duration <= 0) return;

    const deadline = Date.now() + duration;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, deadline - Date.now());
      setRetryRemainingMs(remaining);
      if (remaining === 0) window.clearInterval(timer);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [error?.retryAfterMs]);

  const charCount = value.length;
  const isOverLimit = charCount > MAX_CHARS;
  const isEmpty = value.trim().length === 0;
  const canSubmit = !isEmpty && !isOverLimit && !loading && retryRemainingMs <= 0;

  const handleSubmit = useCallback(() => {
    if (canSubmit) {
      onSubmit(value.trim());
    }
  }, [canSubmit, onSubmit, value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleExampleClick = (text: string) => {
    setValue(text);
    textareaRef.current?.focus();
  };

  if (loading) {
    return <LoadingPipeline />;
  }

  return (
    <section className="input-hero" aria-labelledby="hero-heading">
      <h1 id="hero-heading" className="hero-headline">
        Describe your day.
        <br />
        Get one that actually fits.
      </h1>
      <p className="hero-subtitle">
        Verified stops, real hours, and the shortest feasible order.
      </p>

      <form
        className="prompt-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        aria-label="Plan your day"
      >
        <div className="textarea-wrapper">
          <textarea
            ref={textareaRef}
            className={`prompt-input ${isOverLimit ? 'prompt-input--error' : ''}`}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Venice, 09:00–17:00, architecture and quiet streets, on foot"
            rows={3}
            aria-label="Describe your day"
            aria-describedby="char-count privacy-note"
            aria-invalid={isOverLimit || undefined}
          />
          <span
            id="char-count"
            className={`char-count ${isOverLimit ? 'char-count--error' : ''}`}
            aria-live="polite"
          >
            {charCount} / {MAX_CHARS}
          </span>
        </div>

        {error && (
          <div className="input-error" role="alert">
            {error.message}
            {retryRemainingMs > 0 && (
              <span className="retry-countdown">
                {' '}Retry available in {formatRetryTime(retryRemainingMs)}.
              </span>
            )}
          </div>
        )}

        <button
          type="submit"
          className="submit-button"
          disabled={!canSubmit}
        >
          Build my day
        </button>
      </form>

      <div className="examples-section">
        <span className="examples-label">Try an example</span>
        <div className="examples-row" role="group" aria-label="Example requests">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              className="example-button"
              type="button"
              onClick={() => handleExampleClick(ex.text)}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <p id="privacy-note" className="privacy-note">
        Do not enter sensitive personal information.{' '}
        <a href="/privacy">Privacy policy</a>.
      </p>

      <style>{styles}</style>
    </section>
  );
}

const styles = `
.input-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding-top: var(--space-8);
  max-width: 640px;
  margin: 0 auto;
}

.hero-headline {
  font-family: var(--font-display);
  font-size: 38px;
  line-height: 42px;
  font-weight: 500;
  color: var(--color-ink);
  margin-bottom: var(--space-3);
}

@media (min-width: 640px) {
  .hero-headline {
    font-size: 48px;
    line-height: 52px;
  }
}

.hero-subtitle {
  font-size: 17px;
  line-height: 27px;
  color: var(--color-ink-muted);
  margin-bottom: var(--space-7);
}

.prompt-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.textarea-wrapper {
  position: relative;
  width: 100%;
}

.prompt-input {
  width: 100%;
  min-height: 88px;
  padding: var(--space-4);
  padding-bottom: var(--space-6);
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-input);
  resize: vertical;
  transition: border-color var(--duration-fast) ease;
}

.prompt-input:focus-visible {
  border-color: var(--color-primary);
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}

.prompt-input--error {
  border-color: var(--color-danger);
}

.char-count {
  position: absolute;
  bottom: var(--space-2);
  right: var(--space-3);
  font-size: 12px;
  font-weight: 500;
  color: var(--color-ink-muted);
  font-variant-numeric: tabular-nums;
}

.char-count--error {
  color: var(--color-danger);
}

.input-error {
  font-size: 14px;
  color: var(--color-danger);
  background: var(--color-danger-soft);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-input);
  text-align: left;
}

.submit-button {
  width: 100%;
  min-height: 52px;
  font-size: 16px;
  font-weight: 600;
  color: #ffffff;
  background: var(--color-primary);
  border-radius: var(--radius-input);
  transition: background var(--duration-fast) ease;
}

.submit-button:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.submit-button:disabled {
  opacity: 0.45;
}

.examples-section {
  margin-top: var(--space-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.examples-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink-muted);
}

.examples-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}

.example-button {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  padding: var(--space-2) var(--space-4);
  min-height: 44px;
  transition: background var(--duration-fast) ease;
}

.example-button:hover {
  background: var(--color-accent-lilac);
}

.privacy-note {
  margin-top: var(--space-5);
  font-size: 12px;
  color: var(--color-ink-muted);
}

.privacy-note a {
  color: var(--color-ink-muted);
}
`;
