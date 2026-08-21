import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PromptError from '../src/components/PromptError';

describe('PromptError', () => {
  it('explains a refused prompt instead of only naming the code', () => {
    render(
      <PromptError
        error={{ code: 'OFF_TOPIC', message: 'Please describe a day of sightseeing in a city' }}
      />,
    );
    expect(screen.getByRole('heading', { name: 'That is not a day out' })).toBeInTheDocument();
    // The cause, not just the symptom.
    expect(screen.getByText(/checks that before calling any paid service/)).toBeInTheDocument();
    // Actionable steps.
    expect(screen.getByText('Name one city.')).toBeInTheDocument();
  });

  it('tells the reader what makes an origin unambiguous', () => {
    render(
      <PromptError
        error={{
          code: 'ORIGIN_NOT_FOUND',
          message: 'Could not resolve the requested starting point unambiguously',
        }}
      />,
    );
    expect(
      screen.getByRole('heading', { name: 'The starting point was ambiguous' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Name a specific landmark, square, or station.')).toBeInTheDocument();
  });

  it('always keeps the authoritative server message and code visible', () => {
    render(
      <PromptError
        error={{ code: 'ORIGIN_NOT_FOUND', message: 'Could not resolve the requested starting point' }}
      />,
    );
    expect(screen.getByText('ORIGIN_NOT_FOUND')).toBeInTheDocument();
    expect(
      screen.getByText('Could not resolve the requested starting point'),
    ).toBeInTheDocument();
  });

  it('loads a working prompt when a suggestion is chosen', async () => {
    const onUseSuggestion = vi.fn();
    const user = userEvent.setup();
    render(
      <PromptError
        error={{ code: 'OFF_TOPIC', message: 'off topic' }}
        onUseSuggestion={onUseSuggestion}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'A day in Naples' }));
    expect(onUseSuggestion).toHaveBeenCalledTimes(1);
    expect(onUseSuggestion.mock.calls[0]![0]).toContain('Piazza del Plebiscito in Naples');
  });

  it('offers no suggestions when a better prompt is not the fix', () => {
    render(<PromptError error={{ code: 'PROVIDER_UNAVAILABLE', message: 'upstream down' }} />);
    expect(screen.queryByText('Load one that works')).not.toBeInTheDocument();
    expect(screen.getByText(/not something your prompt caused/)).toBeInTheDocument();
  });

  it('shows the cooldown for a rate limit', () => {
    render(
      <PromptError
        error={{ code: 'RATE_LIMITED', message: 'too many requests', retryAfterMs: 120_000 }}
        retryRemainingMs={120_000}
        formatRetryTime={() => '2 min'}
      />,
    );
    expect(screen.getByText('2 min')).toBeInTheDocument();
    expect(screen.getByText(/five planned days per hour/)).toBeInTheDocument();
  });

  it('falls back to a usable panel for a code it does not know', () => {
    render(<PromptError error={{ code: 'SOMETHING_NEW', message: 'unexpected' }} />);
    expect(screen.getByRole('heading', { name: 'That day could not be built' })).toBeInTheDocument();
    expect(screen.getByText('SOMETHING_NEW')).toBeInTheDocument();
  });

  it('separates a deliberate refusal from a service fault visually', () => {
    const { container: refused } = render(
      <PromptError error={{ code: 'OFF_TOPIC', message: 'x' }} />,
    );
    expect(refused.querySelector('.prompt-error--refused')).not.toBeNull();

    const { container: broken } = render(
      <PromptError error={{ code: 'INTERNAL_ERROR', message: 'x' }} />,
    );
    // A refusal must not be dressed as a failure; only a real fault gets danger styling.
    expect(broken.querySelector('.prompt-error--unavailable')).not.toBeNull();
    expect(broken.querySelector('.prompt-error--refused')).toBeNull();
  });
});
