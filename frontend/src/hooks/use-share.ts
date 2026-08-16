import { useState, useCallback } from 'react';
import type { ItineraryResponse, CreateShareResponse } from '../lib/types';
import { createShare, deleteShare, ApiClientError } from '../lib/api-client';

const DELETION_TOKEN_PREFIX = 'vialo_share_';

function getStoredToken(shareId: string): string | null {
  try {
    return localStorage.getItem(`${DELETION_TOKEN_PREFIX}${shareId}`);
  } catch {
    return null;
  }
}

function storeToken(shareId: string, token: string): void {
  try {
    localStorage.setItem(`${DELETION_TOKEN_PREFIX}${shareId}`, token);
  } catch {
    // Storage unavailable — token won't persist
  }
}

function clearToken(shareId: string): void {
  try {
    localStorage.removeItem(`${DELETION_TOKEN_PREFIX}${shareId}`);
  } catch {
    // Ignore
  }
}

export type ShareState = 'idle' | 'creating' | 'created' | 'error' | 'deleting' | 'deleted';

export interface UseShareReturn {
  state: ShareState;
  shareUrl: string | null;
  shareId: string | null;
  error: string | null;
  canDelete: boolean;
  create: (itinerary: ItineraryResponse) => Promise<string | null>;
  copyLink: () => Promise<boolean>;
  remove: () => Promise<boolean>;
}

export function useShare(existingShareId?: string): UseShareReturn {
  const [state, setState] = useState<ShareState>('idle');
  const [shareResponse, setShareResponse] = useState<CreateShareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const shareId = shareResponse?.shareId ?? existingShareId ?? null;
  const shareUrl = shareResponse?.shareUrl ?? null;
  const canDelete = shareId ? getStoredToken(shareId) !== null : false;

  const create = useCallback(async (itinerary: ItineraryResponse): Promise<string | null> => {
    if (state === 'creating') return null;
    setState('creating');
    setError(null);
    try {
      const response = await createShare(itinerary);
      setShareResponse(response);
      storeToken(response.shareId, response.deletionToken);
      setState('created');
      return response.shareUrl;
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Could not create share link. Try again.');
      }
      setState('error');
      return null;
    }
  }, [state]);

  const copyLink = useCallback(async (): Promise<boolean> => {
    const url = shareUrl ?? (shareId ? `${window.location.origin}/r/${shareId}` : null);
    if (!url) return false;
    try {
      await navigator.clipboard.writeText(url);
      return true;
    } catch {
      return false;
    }
  }, [shareUrl, shareId]);

  const remove = useCallback(async (): Promise<boolean> => {
    if (!shareId) return false;
    const token = getStoredToken(shareId);
    if (!token) return false;

    setState('deleting');
    try {
      await deleteShare(shareId, token);
      clearToken(shareId);
      setState('deleted');
      return true;
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message);
      } else {
        setError('Could not delete share. Try again.');
      }
      setState('error');
      return false;
    }
  }, [shareId]);

  return { state, shareUrl, shareId, error, canDelete, create, copyLink, remove };
}

export { getStoredToken };
