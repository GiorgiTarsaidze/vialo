import { describe, it, expect, vi, beforeEach } from 'vitest';

// We need to test the cognito module — mock crypto.subtle and sessionStorage
const mockDigest = vi.fn();
const mockGetRandomValues = vi.fn((arr: Uint8Array) => {
  for (let i = 0; i < arr.length; i++) arr[i] = i % 256;
  return arr;
});

Object.defineProperty(globalThis, 'crypto', {
  value: {
    getRandomValues: mockGetRandomValues,
    subtle: { digest: mockDigest },
  },
  writable: true,
});

// Mock fetch for token exchange
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// Mock import.meta.env
vi.stubEnv('VITE_COGNITO_DOMAIN', '');
vi.stubEnv('VITE_COGNITO_CLIENT_ID', '');

describe('cognito session', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('getSession returns null when no session stored', async () => {
    const { getSession } = await import('../src/lib/cognito');
    expect(getSession()).toBeNull();
  });

  it('saveSession and getSession roundtrip', async () => {
    const { saveSession, getSession } = await import('../src/lib/cognito');
    saveSession('my-token', 3600);
    const session = getSession();
    expect(session).not.toBeNull();
    expect(session!.idToken).toBe('my-token');
    expect(session!.expiresAt).toBeGreaterThan(Date.now());
  });

  it('getSession returns null when token is expired', async () => {
    const { getSession } = await import('../src/lib/cognito');
    localStorage.setItem('vialo.journal.session', JSON.stringify({
      idToken: 'expired-token',
      expiresAt: Date.now() - 1000,
    }));
    expect(getSession()).toBeNull();
  });

  it('getSession returns null when token is within 60s of expiry', async () => {
    const { getSession } = await import('../src/lib/cognito');
    localStorage.setItem('vialo.journal.session', JSON.stringify({
      idToken: 'soon-expired',
      expiresAt: Date.now() + 30_000, // 30s from now, within 60s threshold
    }));
    expect(getSession()).toBeNull();
  });

  it('clearSession removes session from storage', async () => {
    const { saveSession, clearSession, getSession } = await import('../src/lib/cognito');
    saveSession('token', 3600);
    expect(getSession()).not.toBeNull();
    clearSession();
    expect(getSession()).toBeNull();
  });

  it('isAuthenticated reflects session state', async () => {
    const { isAuthenticated, saveSession, clearSession } = await import('../src/lib/cognito');
    expect(isAuthenticated()).toBe(false);
    saveSession('token', 3600);
    expect(isAuthenticated()).toBe(true);
    clearSession();
    expect(isAuthenticated()).toBe(false);
  });
});

describe('cognito exchangeCode', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('returns error on state mismatch', async () => {
    sessionStorage.setItem('vialo.journal.auth_state', 'expected-state');
    sessionStorage.setItem('vialo.journal.pkce_verifier', 'verifier');

    const { exchangeCode } = await import('../src/lib/cognito');
    const result = await exchangeCode('code123', 'wrong-state');
    expect(result.success).toBe(false);
    expect(result.error).toContain('State mismatch');
  });

  it('returns error when verifier is missing', async () => {
    sessionStorage.setItem('vialo.journal.auth_state', 'my-state');
    // No verifier stored

    const { exchangeCode } = await import('../src/lib/cognito');
    const result = await exchangeCode('code123', 'my-state');
    expect(result.success).toBe(false);
    expect(result.error).toContain('PKCE verifier');
  });

  it('exchanges code successfully and saves session', async () => {
    sessionStorage.setItem('vialo.journal.auth_state', 'my-state');
    sessionStorage.setItem('vialo.journal.pkce_verifier', 'my-verifier');
    sessionStorage.setItem('vialo.journal.auth_return', '/journal/new');

    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id_token: 'new-id-token', access_token: 'at', expires_in: 3600 }),
    });

    const { exchangeCode, getSession } = await import('../src/lib/cognito');
    const result = await exchangeCode('code123', 'my-state');
    expect(result.success).toBe(true);
    expect(result.returnPath).toBe('/journal/new');

    // Session should be saved
    const session = getSession();
    expect(session).not.toBeNull();
    expect(session!.idToken).toBe('new-id-token');

    // sessionStorage should be cleaned up
    expect(sessionStorage.getItem('vialo.journal.auth_state')).toBeNull();
    expect(sessionStorage.getItem('vialo.journal.pkce_verifier')).toBeNull();
    expect(sessionStorage.getItem('vialo.journal.auth_return')).toBeNull();
  });

  it('returns error on fetch failure', async () => {
    sessionStorage.setItem('vialo.journal.auth_state', 'my-state');
    sessionStorage.setItem('vialo.journal.pkce_verifier', 'my-verifier');

    mockFetch.mockResolvedValue({ ok: false, status: 400, json: () => Promise.resolve({}) });

    const { exchangeCode } = await import('../src/lib/cognito');
    const result = await exchangeCode('code123', 'my-state');
    expect(result.success).toBe(false);
    expect(result.error).toContain('Token exchange failed');
  });

  it('returns error on network error', async () => {
    sessionStorage.setItem('vialo.journal.auth_state', 'my-state');
    sessionStorage.setItem('vialo.journal.pkce_verifier', 'my-verifier');

    mockFetch.mockRejectedValue(new Error('network error'));

    const { exchangeCode } = await import('../src/lib/cognito');
    const result = await exchangeCode('code123', 'my-state');
    expect(result.success).toBe(false);
    expect(result.error).toContain('Network error');
  });
});
