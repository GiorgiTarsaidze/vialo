import { useState, useRef, useCallback, useEffect } from 'react';
import type { PlanningError } from '../hooks/use-planning';
import type { PlanningPayload } from '../lib/types';
import { useAutocomplete } from '../hooks/use-autocomplete';
import PlaceAutocomplete from './PlaceAutocomplete';
import SelectionMap from './SelectionMap';
import LoadingPipeline from './LoadingPipeline';
import PromptError from './PromptError';

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

/** Animated postcard/route SVG composition for the hero background */
function HeroPostcard() {
  return (
    <div className="hero-postcard" aria-hidden="true">
      <svg
        className="postcard-svg"
        viewBox="0 0 360 180"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        role="presentation"
      >
        {/* Skyline silhouette shapes */}
        <rect className="postcard-building postcard-building--1" x="20" y="90" width="28" height="70" rx="3" fill="var(--color-primary-soft)" />
        <rect className="postcard-building postcard-building--2" x="55" y="70" width="22" height="90" rx="3" fill="var(--color-accent-lilac)" />
        <rect className="postcard-building postcard-building--3" x="84" y="80" width="30" height="80" rx="3" fill="var(--color-accent-blush)" />
        <rect className="postcard-building postcard-building--4" x="280" y="75" width="26" height="85" rx="3" fill="var(--color-primary-soft)" />
        <rect className="postcard-building postcard-building--5" x="312" y="85" width="30" height="75" rx="3" fill="var(--color-accent-lilac)" />

        {/* Church/landmark dome */}
        <path className="postcard-building postcard-building--2" d="M65 70 Q66 55 76 55 Q86 55 87 70" fill="var(--color-accent-lilac)" />

        {/* Ground plane */}
        <rect x="0" y="160" width="360" height="20" fill="var(--color-border)" opacity="0.4" />

        {/* Route path (animated) */}
        <path
          className="postcard-route"
          d="M 30 155 C 60 140 100 148 140 145 S 200 135 240 140 S 300 148 340 152"
          stroke="var(--color-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          fill="none"
        />

        {/* Stop markers along route */}
        <circle className="postcard-stop postcard-stop--1" cx="70" cy="148" r="5" fill="var(--color-primary)" />
        <circle className="postcard-stop postcard-stop--2" cx="155" cy="143" r="5" fill="var(--color-primary)" />
        <circle className="postcard-stop postcard-stop--3" cx="250" cy="139" r="5" fill="var(--color-primary)" />
        <circle className="postcard-stop postcard-stop--4" cx="330" cy="151" r="5" fill="var(--color-primary)" />

        {/* Origin marker */}
        <circle cx="30" cy="155" r="7" fill="var(--color-ink)" stroke="#fff" strokeWidth="2" />
        <text x="30" y="159" textAnchor="middle" fontSize="8" fontWeight="700" fill="#fff">S</text>

        {/* Progress dot that moves along the path */}
        <circle className="postcard-progress" cx="0" cy="0" r="4" fill="var(--color-accent-sun)">
          <animateMotion
            className="postcard-motion"
            dur="3s"
            repeatCount="1"
            fill="freeze"
            path="M 30 155 C 60 140 100 148 140 145 S 200 135 240 140 S 300 148 340 152"
          />
        </circle>
      </svg>

      {/* Floating "postcard" cards */}
      <div className="postcard-card postcard-card--1">
        <span className="postcard-card-time">09:40</span>
        <span className="postcard-card-dot" />
        <span className="postcard-card-name">Basilica</span>
      </div>
      <div className="postcard-card postcard-card--2">
        <span className="postcard-card-time">11:20</span>
        <span className="postcard-card-dot" />
        <span className="postcard-card-name">Palazzo</span>
      </div>
    </div>
  );
}

/** Accessible switch for "End where I started" */
function ReturnSwitch({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-labelledby="return-switch-text"
      className={`return-switch-row ${checked ? 'return-switch-row--on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="return-switch-track" aria-hidden="true">
        <span className="return-switch-thumb" />
      </span>
      <span className="return-switch-label" id="return-switch-text">
        End where I started
      </span>
    </button>
  );
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
    // Examples and error suggestions are both free text, so switch to that tab
    // rather than silently filling a field the user cannot see.
    setMode('free');
    setValue(text);
    textareaRef.current?.focus();
  };

  if (loading) {
    return <LoadingPipeline />;
  }

  return (
    <section className="input-hero" aria-labelledby="hero-heading">
      <HeroPostcard />

      <div className="hero-content">
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
                <ReturnSwitch
                  checked={returnToStart}
                  onChange={setReturnToStart}
                />

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
            <PromptError
              error={error}
              retryRemainingMs={retryRemainingMs}
              formatRetryTime={formatRetryTime}
              onUseSuggestion={handleExampleClick}
            />
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
      </div>

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
  max-width: 640px;
  margin: 0 auto;
  position: relative;
}

/* Postcard animation */
.hero-postcard {
  position: relative;
  width: 100%;
  max-width: 400px;
  margin-bottom: var(--space-5);
  overflow: hidden;
}

.postcard-svg {
  width: 100%;
  height: auto;
  display: block;
}

/* Building entrance animations */
.postcard-building {
  opacity: 0;
  transform: translateY(20px);
  animation: postcard-enter 0.6s ease-out forwards;
}
.postcard-building--1 { animation-delay: 0.1s; }
.postcard-building--2 { animation-delay: 0.2s; }
.postcard-building--3 { animation-delay: 0.3s; }
.postcard-building--4 { animation-delay: 0.15s; }
.postcard-building--5 { animation-delay: 0.25s; }

/* Stop marker entrance */
.postcard-stop {
  opacity: 0;
  transform: scale(0);
  animation: postcard-pop 0.3s ease-out forwards;
}
.postcard-stop--1 { animation-delay: 0.8s; }
.postcard-stop--2 { animation-delay: 1.0s; }
.postcard-stop--3 { animation-delay: 1.2s; }
.postcard-stop--4 { animation-delay: 1.4s; }

/* Route line draw */
.postcard-route {
  stroke-dasharray: 400;
  stroke-dashoffset: 400;
  animation: postcard-draw 1.5s ease-out 0.5s forwards;
}

/* Progress dot — settles at end */
.postcard-progress {
  opacity: 0;
  animation: postcard-fade-in 0.3s ease-out 1s forwards;
}

/* Floating schedule cards */
.postcard-card {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 500;
  color: var(--color-ink);
  box-shadow: 0 2px 8px rgb(43 35 38 / 0.06);
  opacity: 0;
  transform: translateY(8px);
  animation: postcard-card-enter 0.4s ease-out forwards;
}
.postcard-card--1 {
  top: 18%;
  left: 8%;
  animation-delay: 1.2s;
}
.postcard-card--2 {
  top: 24%;
  right: 6%;
  animation-delay: 1.5s;
}
.postcard-card-time {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: var(--color-primary);
}
.postcard-card-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.postcard-card-name {
  color: var(--color-ink-muted);
}

@keyframes postcard-enter {
  to { opacity: 1; transform: translateY(0); }
}
@keyframes postcard-pop {
  to { opacity: 1; transform: scale(1); }
}
@keyframes postcard-draw {
  to { stroke-dashoffset: 0; }
}
@keyframes postcard-fade-in {
  to { opacity: 1; }
}
@keyframes postcard-card-enter {
  to { opacity: 1; transform: translateY(0); }
}

/* Reduced motion: show final state immediately, no perpetual motion */
@media (prefers-reduced-motion: reduce) {
  .postcard-building,
  .postcard-stop,
  .postcard-route,
  .postcard-progress,
  .postcard-card {
    animation: none !important;
    opacity: 1;
    transform: none;
    stroke-dashoffset: 0;
  }
  .postcard-motion {
    display: none;
  }
}

.hero-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
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

/* Accessible switch control */
.return-switch-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-height: 44px;
  width: max-content;
  padding: 0;
  color: var(--color-ink);
  cursor: pointer;
}

.return-switch-row:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
  border-radius: var(--radius-input);
}

.return-switch-track {
  position: relative;
  width: 48px;
  height: 28px;
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  background: var(--color-border-strong);
  transition: background var(--duration-fast) ease;
}

.return-switch-row--on .return-switch-track {
  background: var(--color-primary);
}

.return-switch-thumb {
  position: absolute;
  top: 4px;
  left: 4px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #ffffff;
  box-shadow: 0 1px 3px rgb(43 35 38 / 0.15);
  transition: transform var(--duration-fast) ease;
}

.return-switch-row--on .return-switch-thumb {
  transform: translateX(20px);
}

.return-switch-label {
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
