import { useState, useCallback, useRef } from 'react';
import type { ItineraryResponse } from '../lib/types';
import { planItinerary, ApiClientError } from '../lib/api-client';

export type PlanningState = 'idle' | 'loading' | 'error' | 'result';

export interface PlanningError {
  code: string;
  message: string;
  retryAfterMs?: number;
}

interface PlanningIdle {
  state: 'idle';
  result: null;
  error: null;
  submit: (prompt: string) => void;
  reset: () => void;
}

interface PlanningLoading {
  state: 'loading';
  result: null;
  error: null;
  submit: (prompt: string) => void;
  reset: () => void;
}

interface PlanningErrorState {
  state: 'error';
  result: null;
  error: PlanningError;
  submit: (prompt: string) => void;
  reset: () => void;
}

interface PlanningResult {
  state: 'result';
  result: ItineraryResponse;
  error: null;
  submit: (prompt: string) => void;
  reset: () => void;
}

export type PlanningHook = PlanningIdle | PlanningLoading | PlanningErrorState | PlanningResult;

export function usePlanning(): PlanningHook {
  const [state, setState] = useState<PlanningState>('idle');
  const [result, setResult] = useState<ItineraryResponse | null>(null);
  const [error, setError] = useState<PlanningError | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setState('idle');
    setResult(null);
    setError(null);
  }, []);

  const submit = useCallback(async (prompt: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState('loading');
    setError(null);
    setResult(null);

    try {
      const response = await planItinerary(prompt, controller.signal);
      if (!controller.signal.aborted) {
        setResult(response);
        setState('result');
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      if (err instanceof ApiClientError) {
        const planningError: PlanningError = {
          code: err.code,
          message: getUserMessage(err.code, err.message),
        };
        if (err.code === 'RATE_LIMITED') {
          planningError.retryAfterMs = err.retryAfterMs ?? 3600000;
        }
        setError(planningError);
      } else {
        setError({
          code: 'NETWORK_ERROR',
          message: 'Could not reach the server. Check your connection and try again.',
        });
      }
      setState('error');
    }
  }, []);

  return { state, result, error, submit, reset } as PlanningHook;
}

function getUserMessage(code: string, fallback: string): string {
  switch (code) {
    case 'RATE_LIMITED':
      return 'You have reached the request limit. Try again in an hour.';
    case 'OFF_TOPIC':
      return 'Vialo builds day itineraries for city sightseeing. Describe a city, time window, and what you would like to see.';
    case 'INVALID_INPUT':
      return fallback || 'Please check your input and try again.';
    case 'PROVIDER_UNAVAILABLE':
      return 'The service is temporarily unavailable. Please try again in a moment.';
    case 'AI_BUDGET_EXCEEDED':
      return 'The service is temporarily unavailable. Please try again later.';
    case 'NO_FEASIBLE_ITINERARY':
      return 'No feasible schedule could be built. Try a wider time window or fewer stops.';
    default:
      return fallback || 'Something went wrong. Please try again.';
  }
}
