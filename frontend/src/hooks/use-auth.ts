/**
 * Auth hook for Vialo Journal — exposes session state and actions.
 */
import { useState, useCallback, useEffect } from 'react';
import { getSession, startSignIn, signOut, isAuthenticated, clearSession } from '../lib/cognito';

export interface AuthState {
  authenticated: boolean;
  userId: string | null;
  /** Who the viewer is signed in as. Never an email address. */
  displayName: string | null;
  signIn: (returnPath?: string) => Promise<void>;
  signOutUser: () => void;
}

function parseIdTokenPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = parts[1]!;
    const padded = payload.replace(/-/g, '+').replace(/_/g, '/');
    const json = atob(padded);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

/**
 * Derive the signed-in name shown in the header.
 *
 * Deliberately mirrors `display_name_from_claims` in the backend, including the
 * claim order and the `Traveller` fallback, so the header never disagrees with
 * the name attached to a published story. Only the local part of an email is
 * ever used: the full address is not displayed anywhere in the UI.
 */
export function displayNameFromClaims(claims: Record<string, unknown> | null): string | null {
  if (!claims) return null;
  for (const key of ['nickname', 'preferred_username', 'name', 'given_name']) {
    const value = claims[key];
    if (typeof value === 'string' && value.trim()) return value.trim().slice(0, 40);
  }
  const email = claims['email'];
  if (typeof email === 'string' && email.includes('@')) {
    const local = email.split('@')[0]!.trim();
    if (local) return local.slice(0, 40);
  }
  return 'Traveller';
}

function readIdentity(): { userId: string | null; displayName: string | null } {
  const session = getSession();
  if (!session) return { userId: null, displayName: null };
  const payload = parseIdTokenPayload(session.idToken);
  return {
    userId: (payload?.['sub'] as string) ?? null,
    displayName: displayNameFromClaims(payload),
  };
}

export function useAuth(): AuthState {
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated());
  const [identity, setIdentity] = useState(readIdentity);

  // Periodically check token expiry
  useEffect(() => {
    const interval = setInterval(() => {
      const valid = isAuthenticated();
      if (!valid && authenticated) {
        setAuthenticated(false);
        setIdentity({ userId: null, displayName: null });
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [authenticated]);

  // Listen for storage events (other tabs)
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === 'vialo.journal.session') {
        const valid = isAuthenticated();
        setAuthenticated(valid);
        setIdentity(valid ? readIdentity() : { userId: null, displayName: null });
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  const signIn = useCallback(async (returnPath?: string) => {
    await startSignIn(returnPath);
  }, []);

  const signOutUser = useCallback(() => {
    clearSession();
    setAuthenticated(false);
    setIdentity({ userId: null, displayName: null });
    signOut();
  }, []);

  return {
    authenticated,
    userId: identity.userId,
    displayName: identity.displayName,
    signIn,
    signOutUser,
  };
}
