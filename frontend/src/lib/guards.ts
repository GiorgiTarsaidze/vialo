/**
 * Runtime type guards for API responses.
 * Validate shape before rendering to prevent rendering garbage from malformed responses.
 */
import type { ItineraryResponse, CreateShareResponse, ApiError } from './types';

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

export function isApiError(v: unknown): v is ApiError {
  if (!isObject(v)) return false;
  const err = v['error'];
  if (!isObject(err)) return false;
  return typeof err['code'] === 'string' && typeof err['message'] === 'string';
}

export function isItineraryResponse(v: unknown): v is ItineraryResponse {
  if (!isObject(v)) return false;
  if (v['schemaVersion'] !== 1) return false;
  if (typeof v['requestId'] !== 'string') return false;
  if (v['status'] !== 'complete' && v['status'] !== 'partial') return false;
  if (!isObject(v['locality'])) return false;
  if (typeof (v['locality'] as Record<string, unknown>)['name'] !== 'string') return false;
  if (v['travelMode'] !== 'WALK' && v['travelMode'] !== 'DRIVE') return false;
  if (!isObject(v['window'])) return false;
  if (!isObject(v['origin'])) return false;
  if (!Array.isArray(v['stops'])) return false;
  if (!Array.isArray(v['timeline'])) return false;
  if (!Array.isArray(v['droppedStops'])) return false;
  if (!isObject(v['comparison'])) return false;
  if (!isObject(v['mapsHandoff'])) return false;
  if (!isObject(v['totals'])) return false;
  if (!Array.isArray(v['diagnostics'])) return false;
  return true;
}

export function isCreateShareResponse(v: unknown): v is CreateShareResponse {
  if (!isObject(v)) return false;
  return (
    typeof v['shareId'] === 'string' &&
    typeof v['shareUrl'] === 'string' &&
    typeof v['deletionToken'] === 'string'
  );
}
