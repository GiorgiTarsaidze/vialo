import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  MAPS_AUTH_FAILURE_EVENT,
  notifyMapsAuthFailure,
} from '../src/lib/google-maps';

describe('Google Maps authentication failures', () => {
  afterEach(() => {
    window.__vialoMapsAuthFailed = false;
  });

  it('sets shared failure state and notifies mounted map components', () => {
    const listener = vi.fn();
    window.addEventListener(MAPS_AUTH_FAILURE_EVENT, listener);

    notifyMapsAuthFailure();

    expect(window.__vialoMapsAuthFailed).toBe(true);
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(MAPS_AUTH_FAILURE_EVENT, listener);
  });
});
