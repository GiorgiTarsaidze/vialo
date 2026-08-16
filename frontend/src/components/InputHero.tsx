import { useState, useRef, useCallback, useEffect } from 'react';
import type { PlanningError } from '../hooks/use-planning';
import type { PlanningPayload } from '../lib/types';
import { useAutocomplete } from '../hooks/use-autocomplete';
import PlaceAutocomplete from './PlaceAutocomplete';
import SelectionMap from './SelectionMap';
import LoadingPipeline from './LoadingPipeline';

const MAX_CHARS = 500;

const EXAMPLES = [
  {
    label: 'Venice morning',
    text: 'Tomorrow, start at Piazzale Roma in Venice at 09:00. Plan a walking day until 14:00 with architecture, churches, and quiet streets.',
  },
  {
    label: 'Naples highlights',
    text: 'Tomorrow, start at Piazza del Plebiscito in Naples at 10:00. Plan a walking day until 18:00 with the main highlights and great pizza for lunch.',
  },
  {
    label: 'Lisbon viewpoints',
    text: 'Tomorrow, start at Praça do Comércio in Lisbon at 08:30. Plan a walking day until 16:00 with miradouros and tile work.',
  },
];

export type InputMode = 'free' | 'structured';

function formatRetryTime(milliseconds: number): string {
  const totalSeconds = Math.max(1, Math.ceil(milliseconds / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;
}

interface InputHeroProps {
  onSubmit: (payload: string | PlanningPayload) => void;
  loading?: boolean;
  error?: PlanningError | null;
}

export default function InputHero({ onSubmit, loading, error }: InputHeroProps) {
  const [mode, setMode] = useState<InputMode>('free');
  const [value, setValue] = useState('');
  const [structuredPrompt, setStructuredPrompt] = useState('');
  const [returnToStart, setReturnToStart] = useState(true);
  const [retryRemainingMs, setRetryRemainingMs] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const structuredTextareaRef = useRef<HTMLTextAreaElement>(null);

  const originAutocomplete = useAutocomplete('origin');
  const destinationAutocomplete = useAutocomplete('destination');

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

  // Free mode validation
  const charCount = value.length;
  const isOverLimit = charCount > MAX_CHARS;
  const isEmpty = value.trim().length === 0;

  // Structured mode validation
  const structuredCharCount = structuredPrompt.length;
  const isStructuredOverLimit = structuredCharCount > MAX_CHARS;
  const hasOrigin = originAutocomplete.selectedPlace !== null;
  const hasStructuredPrompt = structuredPrompt.trim().length > 0;
  const hasDestination = returnToStart || destinationAutocomplete.selectedPlace !== null;

  const canSubmitFree = !isEmpty && !isOverLimit && !loading && retryRemainingMs <= 0;
  const canSubmitStructured = hasOrigin && hasStructuredPrompt && !isStructuredOverLimit && hasDestination && !loading && retryRemainingMs <= 0;
  const canSubmit = mode === 'free' ? canSubmitFree : canSubmitStructured;

  const handleSubmit = useCallback(() => {
    if (!canSubmit) return;

    if (mode === 'free') {
      onSubmit(value.trim());
    } else {
      const payload: PlanningPayload = {
        prompt: structuredPrompt.trim(),
        origin: originAutocomplete.selectedPlace!,
      };
      if (returnToStart) {
        payload.destination = originAutocomplete.selectedPlace!;
      } else if (destinationAutocomplete.selectedPlace) {
        payload.destination = destinationAutocomplete.selectedPlace;
      }
      onSubmit(payload);
    }
  }, [canSubmit, mode, value, structuredPrompt, originAutocomplete.selectedPlace, destinationAutocomplete.selectedPlace, returnToStart, onSubmit]);

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
      <img
        src="/logo-hero.png"
        alt=""
        className="hero-logo"
        width="64"
        height="64"
      />
      <h1 id="hero-heading" className="hero-headline">
        Describe your day.
        <br />
        Get one that actually fits.
      </h1>
      <p className="hero-subtitle">
        Verified stops, real hours, and the shortest feasible order.
      </p>

      {/* Mode toggle */}
      <div className="mode-toggle" role="tablist" aria-label="Input mode">
        <button
          role="tab"
          aria-selected={mode === 'free'}
          aria-controls="panel-free"
          className={`mode-tab ${mode === 'free' ? 'mode-tab--active' : ''}`}
          onClick={() => setMode('free')}
          type="button"
        >
          Describe freely
        </button>
        <button
          role="tab"
          aria-selected={mode === 'structured'}
          aria-controls="panel-structured"
          className={`mode-tab ${mode === 'structured' ? 'mode-tab--active' : ''}`}
          onClick={() => setMode('structured')}
          type="button"
        >
          Choose details
        </button>
      </div>

      <form
        className="prompt-form"
        onSubmit={(e) => {
          e.preventDefault();
          handleSubmit();
        }}
        aria-label="Plan your day"
      >
        {/* Free mode panel */}
        {mode === 'free' && (
          <div id="panel-free" role="tabpanel" aria-labelledby="hero-heading">
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
          </div>
        )}

        {/* Structured mode panel */}
        {mode === 'structured' && (
          <div id="panel-structured" role="tabpanel" className="structured-panel">
            <PlaceAutocomplete
              autocomplete={originAutocomplete}
              label="Start location"
              placeholder="Search for your starting point…"
              required
            />

            <div className="destination-section">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={returnToStart}
                  onChange={(e) => setReturnToStart(e.target.checked)}
                  className="checkbox-input"
                />
                <span className="checkbox-text">End where I started</span>
              </label>

              {!returnToStart && (
                <PlaceAutocomplete
                  autocomplete={destinationAutocomplete}
                  label="End location"
                  placeholder="Search for your ending point…"
                  required
                />
              )}
            </div>

            <SelectionMap
              origin={originAutocomplete.selectedPlace}
              destination={!returnToStart ? destinationAutocomplete.selectedPlace : null}
            />

            <div className="textarea-wrapper">
              <textarea
                ref={structuredTextareaRef}
                className={`prompt-input ${isStructuredOverLimit ? 'prompt-input--error' : ''}`}
                value={structuredPrompt}
                onChange={(e) => setStructuredPrompt(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="09:00–17:00, architecture and quiet streets, on foot"
                rows={2}
                aria-label="Date, time, and interests"
                aria-describedby="structured-char-count privacy-note"
                aria-invalid={isStructuredOverLimit || undefined}
              />
              <span
                id="structured-char-count"
                className={`char-count ${isStructuredOverLimit ? 'char-count--error' : ''}`}
                aria-live="polite"
              >
                {structuredCharCount} / {MAX_CHARS}
              </span>
            </div>
          </div>
        )}

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

      {mode === 'free' && (
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
      )}

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
  padding-top: var(--space-7);
  max-width: 640px;
  margin: 0 auto;
}

.hero-logo {
  width: 56px;
  height: 56px;
  margin-bottom: var(--space-4);
  border-radius: 12px;
}

@media (min-width: 640px) {
  .hero-logo {
    width: 64px;
    height: 64px;
  }
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
  margin-bottom: var(--space-6);
}

.mode-toggle {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-pill);
  margin-bottom: var(--space-5);
}

.mode-tab {
  font-size: 13px;
  font-weight: 600;
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-pill);
  color: var(--color-ink-muted);
  min-height: 44px;
  transition: all var(--duration-fast) ease;
}

.mode-tab--active {
  color: var(--color-ink);
  background: var(--color-surface-strong);
  box-shadow: 0 1px 3px rgb(43 35 38 / 0.08);
}

.mode-tab:hover:not(.mode-tab--active) {
  color: var(--color-ink);
}

.prompt-form {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  text-align: left;
}

.structured-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.destination-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  min-height: 44px;
}

.checkbox-input {
  width: 18px;
  height: 18px;
  accent-color: var(--color-primary);
  cursor: pointer;
}

.checkbox-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
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
  text-align: center;
}

.privacy-note a {
  color: var(--color-ink-muted);
}
`;
