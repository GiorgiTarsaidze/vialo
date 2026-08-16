/**
 * Typed same-origin API client for Vialo.
 * All requests go to /api/* which CloudFront routes to API Gateway.
 */
import type { ItineraryResponse, CreateShareResponse } from './types';
import { isItineraryResponse, isCreateShareResponse, isApiError } from './guards';

export class ApiClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number,
    public readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

async function handleResponse<T>(
  response: Response,
  guard: (v: unknown) => v is T,
): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (isApiError(body)) {
      const retryAfterHeader = response.headers?.get('Retry-After') ?? null;
      const retryAfterValue = retryAfterHeader ? Number(retryAfterHeader) : Number.NaN;
      const retryAfterMs = Number.isFinite(retryAfterValue)
        ? Math.max(
            0,
            retryAfterValue > 1_000_000_000
              ? retryAfterValue * 1000 - Date.now()
              : retryAfterValue * 1000,
          )
        : undefined;
      throw new ApiClientError(
        body.error.code,
        body.error.message,
        response.status,
        retryAfterMs,
      );
    }
    throw new ApiClientError(
      'UNKNOWN_ERROR',
      `Request failed with status ${response.status}`,
      response.status,
    );
  }

  const data: unknown = await response.json();
  if (!guard(data)) {
    throw new ApiClientError(
      'INVALID_RESPONSE',
      'Server returned an unexpected response format',
      200,
    );
  }
  return data;
}

export async function planItinerary(
  prompt: string,
  signal?: AbortSignal,
): Promise<ItineraryResponse> {
  const response = await fetch('/api/itineraries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
    signal,
  });
  return handleResponse(response, isItineraryResponse);
}

export async function createShare(
  itinerary: ItineraryResponse,
): Promise<CreateShareResponse> {
  if (!itinerary.shareProof) {
    throw new ApiClientError('NO_PROOF', 'Itinerary has no share proof', 400);
  }
  const response = await fetch('/api/shares', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      itinerary,
      proof: itinerary.shareProof,
    }),
  });
  return handleResponse(response, isCreateShareResponse);
}

export async function getShare(shareId: string): Promise<ItineraryResponse> {
  const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}`);
  return handleResponse(response, isItineraryResponse);
}

export async function deleteShare(
  shareId: string,
  deletionToken: string,
): Promise<void> {
  const response = await fetch(`/api/shares/${encodeURIComponent(shareId)}`, {
    method: 'DELETE',
    headers: { 'X-Share-Delete-Token': deletionToken },
  });
  if (!response.ok && response.status !== 204) {
    const body = await response.json().catch(() => null);
    if (isApiError(body)) {
      throw new ApiClientError(body.error.code, body.error.message, response.status);
    }
    throw new ApiClientError('DELETE_FAILED', 'Failed to delete share', response.status);
  }
}
