/**
 * Cognito PKCE auth utilities for Vialo Journal.
 * Authorization Code + PKCE flow, no client secret.
 */

// Public client configuration. Both values are visible in the browser bundle by
// design: a Cognito app client with no secret and a hosted-UI domain are not
// credentials. An empty build-time value falls back to the deployed defaults.
const COGNITO_DOMAIN =
  import.meta.env.VITE_COGNITO_DOMAIN || 'vialo-place-journal.auth.us-east-1.amazoncognito.com';
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID || '6lue0pok3ga0qsnmk8knmcq82l';

const SESSION_KEY = 'vialo.journal.session';
const VERIFIER_KEY = 'vialo.journal.pkce_verifier';
const STATE_KEY = 'vialo.journal.auth_state';
const RETURN_KEY = 'vialo.journal.auth_return';

export interface Session {
  idToken: string;
  expiresAt: number; // absolute ms
}

// --- PKCE helpers ---

function base64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let str = '';
  for (let i = 0; i < bytes.length; i++) {
    str += String.fromCharCode(bytes[i]!);
  }
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function generateRandom(length: number): string {
  const bytes = new Uint8Array(length);
  crypto.getRandomValues(bytes);
  return base64url(bytes.buffer);
}

async function computeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return base64url(digest);
}

// --- Session management ---

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    // Treat as expired if within 60 seconds of expiry
    if (Date.now() >= parsed.expiresAt - 60_000) {
      localStorage.removeItem(SESSION_KEY);
      return null;
    }
    return parsed;
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function getIdToken(): string | null {
  return getSession()?.idToken ?? null;
}

export function saveSession(idToken: string, expiresIn: number): void {
  const session: Session = {
    idToken,
    expiresAt: Date.now() + expiresIn * 1000,
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_KEY);
}

export function isAuthenticated(): boolean {
  return getSession() !== null;
}

// --- Auth flow ---

export function getRedirectUri(): string {
  return `${window.location.origin}/auth/callback`;
}

export async function startSignIn(returnPath?: string): Promise<void> {
  const verifier = generateRandom(32);
  const state = generateRandom(16);
  const challenge = await computeChallenge(verifier);

  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  if (returnPath) {
    sessionStorage.setItem(RETURN_KEY, returnPath);
  }

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    redirect_uri: getRedirectUri(),
    scope: 'openid email profile',
    code_challenge_method: 'S256',
    code_challenge: challenge,
    state,
  });

  window.location.href = `https://${COGNITO_DOMAIN}/oauth2/authorize?${params.toString()}`;
}

export async function startSignUp(returnPath?: string): Promise<void> {
  const verifier = generateRandom(32);
  const state = generateRandom(16);
  const challenge = await computeChallenge(verifier);

  sessionStorage.setItem(VERIFIER_KEY, verifier);
  sessionStorage.setItem(STATE_KEY, state);
  if (returnPath) {
    sessionStorage.setItem(RETURN_KEY, returnPath);
  }

  const params = new URLSearchParams({
    response_type: 'code',
    client_id: CLIENT_ID,
    redirect_uri: getRedirectUri(),
    scope: 'openid email profile',
    code_challenge_method: 'S256',
    code_challenge: challenge,
    state,
  });

  window.location.href = `https://${COGNITO_DOMAIN}/signup?${params.toString()}`;
}

export interface TokenExchangeResult {
  success: boolean;
  error?: string;
  returnPath?: string;
}

export async function exchangeCode(code: string, state: string): Promise<TokenExchangeResult> {
  const savedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(VERIFIER_KEY);

  // Clean up immediately
  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
  const returnPath = sessionStorage.getItem(RETURN_KEY) ?? '/journal';
  sessionStorage.removeItem(RETURN_KEY);

  if (!savedState || state !== savedState) {
    return { success: false, error: 'State mismatch. Please try signing in again.' };
  }
  if (!verifier) {
    return { success: false, error: 'Missing PKCE verifier. Please try signing in again.' };
  }

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: CLIENT_ID,
    code,
    redirect_uri: getRedirectUri(),
    code_verifier: verifier,
  });

  try {
    const response = await fetch(`https://${COGNITO_DOMAIN}/oauth2/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });

    if (!response.ok) {
      return { success: false, error: 'Token exchange failed. Please try signing in again.' };
    }

    const data = await response.json() as { id_token: string; expires_in: number };
    saveSession(data.id_token, data.expires_in);
    return { success: true, returnPath };
  } catch {
    return { success: false, error: 'Network error during sign-in. Please try again.' };
  }
}

export function signOut(): void {
  clearSession();
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    logout_uri: `${window.location.origin}/journal`,
  });
  window.location.href = `https://${COGNITO_DOMAIN}/logout?${params.toString()}`;
}
