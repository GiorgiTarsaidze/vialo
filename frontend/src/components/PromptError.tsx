import type { PlanningError } from '../hooks/use-planning';

/**
 * The typed failure surface for a planning request.
 *
 * The API already returns a stable diagnostic code and a short message, but the
 * short message alone tells someone what went wrong without telling them what to
 * do about it. "Could not resolve the requested starting point unambiguously" is
 * accurate and almost useless if you do not already know the pipeline needs one
 * unambiguous origin.
 *
 * Each code therefore carries a plain headline, an explanation of the cause, and
 * concrete next steps. Where a better prompt is the fix, the suggestions are
 * clickable and load straight into the input.
 *
 * The server's own message is still shown, quietly, at the foot of the panel.
 * Replacing it outright would hide the authoritative text when the two ever
 * disagree.
 */

interface Suggestion {
  label: string;
  prompt: string;
}

interface ErrorCopy {
  title: string;
  cause: string;
  steps: string[];
  suggestions?: Suggestion[];
  tone: 'refused' | 'input' | 'unavailable';
}

const SUGGESTIONS: Suggestion[] = [
  {
    label: 'A morning in Venice',
    prompt:
      'Tomorrow, start at Piazzale Roma in Venice at 09:00. Plan a walking day until 14:00 with architecture, churches, and quiet streets.',
  },
  {
    label: 'A day in Naples',
    prompt:
      'Tomorrow, start at Piazza del Plebiscito in Naples at 10:00. Plan a walking day until 18:00 with the main highlights and great pizza for lunch.',
  },
];

const COPY: Record<string, ErrorCopy> = {
  OFF_TOPIC: {
    tone: 'refused',
    title: 'That is not a day out',
    cause:
      'Vialo only schedules sightseeing days in one city. It checks that before calling any paid service, so a prompt it cannot use costs nothing and is refused rather than guessed at.',
    steps: [
      'Name one city.',
      'Give a start and end time, for example 10:00 to 18:00.',
      'Say what you are interested in: churches, viewpoints, food, markets.',
    ],
    suggestions: SUGGESTIONS,
  },
  ORIGIN_NOT_FOUND: {
    tone: 'input',
    title: 'The starting point was ambiguous',
    cause:
      'Every day is built outward from one exact place, so the origin has to resolve to a single result. Something like "the historic centre" or "my hotel" matches too many places to pick one, and Vialo will not guess which door you meant.',
    steps: [
      'Name a specific landmark, square, or station.',
      'Include the city with it, for example "Piazza del Plebiscito in Naples".',
      'A street address works too.',
    ],
    suggestions: SUGGESTIONS,
  },
  DESTINATION_NOT_FOUND: {
    tone: 'input',
    title: 'The end point was ambiguous',
    cause:
      'The place you asked to finish at did not resolve to a single result, so the day could not be closed off correctly.',
    steps: [
      'Name a specific landmark, square, or station to end at.',
      'Or remove the end point and let the day finish wherever the route lands.',
    ],
  },
  INVALID_TIME_WINDOW: {
    tone: 'input',
    title: 'That time window will not work',
    cause:
      'Vialo schedules one local calendar day. The window has to start before it ends and cannot run past midnight into the next day.',
    steps: [
      'Use a start and end on the same day, for example 09:00 to 17:00.',
      'For an evening, stop at 23:00 rather than crossing midnight.',
    ],
  },
  INVALID_DATE: {
    tone: 'input',
    title: 'That date has already passed',
    cause:
      'The date you asked for is earlier than the current date in the city itself, so opening hours for it cannot be checked.',
    steps: ['Ask for today, tomorrow, or a date in the future.'],
  },
  INVALID_INPUT: {
    tone: 'input',
    title: 'That request could not be read',
    cause: 'The prompt was empty, too long, or missing something the scheduler needs.',
    steps: [
      'Keep it under 500 characters.',
      'Include a city, a time window, and what you want to see.',
    ],
    suggestions: SUGGESTIONS,
  },
  RATE_LIMITED: {
    tone: 'unavailable',
    title: 'You have hit the hourly limit',
    cause:
      'Vialo is free and every day it builds costs real money in place, route, and model calls, so it accepts five planned days per hour.',
    steps: ['Wait for the limit to reset, then try again. Nothing was charged to you.'],
  },
  AI_BUDGET_EXCEEDED: {
    tone: 'unavailable',
    title: 'The monthly budget is spent',
    cause:
      'Vialo caps its own model spending and refuses new requests once the cap is reached, rather than running up a bill.',
    steps: ['Try again after the budget resets at the start of next month.'],
  },
  PROVIDER_UNAVAILABLE: {
    tone: 'unavailable',
    title: 'A service Vialo depends on is down',
    cause:
      'Google Places, Google Routes, or the model service did not answer. This is not something your prompt caused.',
    steps: ['Wait a moment and try again.', 'If it keeps happening, it is on our side, not yours.'],
  },
  NO_REACHABLE_STOPS: {
    tone: 'input',
    title: 'Nothing could be reached from there',
    cause:
      'Every candidate stop was either too far from the starting point to walk to, or could not be verified as a real place.',
    steps: [
      'Start somewhere closer to the centre of the city.',
      'Widen the time window.',
      'Try driving instead of walking for a spread-out city.',
    ],
  },
  NO_FEASIBLE_ITINERARY: {
    tone: 'input',
    title: 'No version of that day fits',
    cause:
      'Between opening hours, travel times, and the length of your window, there is no order of these stops that works.',
    steps: [
      'Give the day more hours.',
      'Move it to a day when more places are open, since many museums close on Mondays.',
    ],
  },
  INTERNAL_ERROR: {
    tone: 'unavailable',
    title: 'Something broke on our side',
    cause: 'The request reached Vialo and failed there. Your prompt was almost certainly fine.',
    steps: ['Try again.', 'If it keeps failing, it is a bug worth reporting.'],
  },
};

const FALLBACK: ErrorCopy = {
  tone: 'unavailable',
  title: 'That day could not be built',
  cause: 'The request did not complete.',
  steps: ['Try again, or adjust the prompt slightly.'],
};

interface PromptErrorProps {
  error: PlanningError;
  /** Remaining cooldown in ms, already counted down by the caller. */
  retryRemainingMs?: number;
  formatRetryTime?: (ms: number) => string;
  /** Loads a suggested prompt into the input. */
  onUseSuggestion?: (prompt: string) => void;
}

export default function PromptError({
  error,
  retryRemainingMs = 0,
  formatRetryTime,
  onUseSuggestion,
}: PromptErrorProps) {
  const copy = COPY[error.code] ?? FALLBACK;
  const showSuggestions = copy.suggestions && copy.suggestions.length > 0 && onUseSuggestion;

  return (
    <div className={`prompt-error prompt-error--${copy.tone}`} role="alert">
      <div className="prompt-error__head">
        <span className="prompt-error__glyph" aria-hidden="true">
          {copy.tone === 'refused' ? '!' : copy.tone === 'input' ? '?' : '~'}
        </span>
        <h3 className="prompt-error__title">{copy.title}</h3>
      </div>

      <p className="prompt-error__cause">{copy.cause}</p>

      {retryRemainingMs > 0 && formatRetryTime && (
        <p className="prompt-error__retry">
          Try again in <strong>{formatRetryTime(retryRemainingMs)}</strong>.
        </p>
      )}

      <ul className="prompt-error__steps">
        {copy.steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ul>

      {showSuggestions && (
        <div className="prompt-error__suggestions">
          <span className="prompt-error__suggestions-label">Load one that works</span>
          <div className="prompt-error__suggestion-row">
            {copy.suggestions!.map((s) => (
              <button
                key={s.label}
                type="button"
                className="prompt-error__suggestion"
                onClick={() => onUseSuggestion!(s.prompt)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="prompt-error__raw">
        <span className="prompt-error__code">{error.code}</span>
        {error.message}
      </p>

      <style>{styles}</style>
    </div>
  );
}

const styles = `
.prompt-error {
  text-align: left;
  padding: var(--space-5);
  border-radius: var(--radius-card);
  border: 1px solid var(--color-border);
  background: var(--color-surface-strong);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  animation: prompt-error-in var(--duration-section) ease both;
}

@keyframes prompt-error-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .prompt-error { animation: none; }
}

/* Refusal is not a failure, so it does not get danger colouring. A prompt Vialo
   declines on purpose reads as a boundary; a service outage reads as a fault. */
.prompt-error--refused {
  background: var(--color-accent-sun-soft);
  border-color: var(--color-accent-sun);
}

.prompt-error--input {
  background: var(--color-primary-soft);
  border-color: var(--color-primary);
}

.prompt-error--unavailable {
  background: var(--color-danger-soft);
  border-color: var(--color-danger);
}

.prompt-error__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.prompt-error__glyph {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: var(--radius-pill);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  color: #ffffff;
}

.prompt-error--refused .prompt-error__glyph { background: var(--color-warning); }
.prompt-error--input .prompt-error__glyph { background: var(--color-primary); }
.prompt-error--unavailable .prompt-error__glyph { background: var(--color-danger); }

.prompt-error__title {
  font-family: var(--font-display);
  font-size: 21px;
  line-height: 26px;
  font-weight: 500;
  color: var(--color-ink);
  margin: 0;
}

.prompt-error__cause {
  font-size: 15px;
  line-height: 23px;
  color: var(--color-ink);
  margin: 0;
}

.prompt-error__retry {
  font-size: 14px;
  color: var(--color-ink);
  margin: 0;
}

.prompt-error__steps {
  margin: 0;
  padding-left: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: 14px;
  line-height: 22px;
  color: var(--color-ink);
}

.prompt-error__suggestions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-1);
}

.prompt-error__suggestions-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.prompt-error__suggestion-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.prompt-error__suggestion {
  min-height: 40px;
  padding: 0 var(--space-4);
  font-size: 13px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-pill);
  transition: background var(--duration-fast) ease, border-color var(--duration-fast) ease;
}

.prompt-error__suggestion:hover {
  background: var(--color-surface);
  border-color: var(--color-ink-muted);
}

/* The authoritative server text, kept visible but subordinate. */
.prompt-error__raw {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-2);
  margin: 0;
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  font-size: 12px;
  line-height: 18px;
  color: var(--color-ink-muted);
}

.prompt-error__code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  background: var(--color-canvas);
  border: 1px solid var(--color-border);
  border-radius: 6px;
  padding: 1px 6px;
}
`;
