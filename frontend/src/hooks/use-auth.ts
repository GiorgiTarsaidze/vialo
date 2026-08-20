/**
 * Auth hook for Vialo Journal — exposes session state and actions.
 */
import { useState, useCallback, useEffect } from 'react';
import { getSession, startSignIn, signOut, isAuthenticated, clearSession } from '../lib/cognito';

export interface AuthState {
  authenticated: boolean;
  userId: string | null;
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

export function useAuth(): AuthState {
  const [authenticated, setAuthenticated] = useState(() => isAuthenticated());
  const [userId, setUserId] = useState<string | null>(() => {
    const session = getSession();
    if (!session) return null;
    const payload = parseIdTokenPayload(session.idToken);
    return (payload?.['sub'] as string) ?? null;
  });

  // Periodically check token expiry
  useEffect(() => {
    const interval = setInterval(() => {
      const valid = isAuthenticated();
      if (!valid && authenticated) {
        setAuthenticated(false);
        setUserId(null);
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
        if (!valid) {
          setUserId(null);
        } else {
          const session = getSession();
          if (session) {
            const payload = parseIdTokenPayload(session.idToken);
            setUserId((payload?.['sub'] as string) ?? null);
          }
        }
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
    setUserId(null);
    signOut();
  }, []);

  return { authenticated, userId, signIn, signOutUser };
}
