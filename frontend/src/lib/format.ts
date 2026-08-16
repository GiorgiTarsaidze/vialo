/**
 * Formatting utilities — distances, durations, times.
 */

/** Format seconds into human-readable duration like "1 hr 04 min" or "6 min" */
export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  if (totalMinutes < 60) {
    return `${totalMinutes} min`;
  }
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  if (mins === 0) return `${hours} hr`;
  return `${hours} hr ${String(mins).padStart(2, '0')} min`;
}

/** Format meters to km with one decimal, or meters if < 1000 */
export function formatDistance(meters: number): string {
  if (meters < 1000) {
    return `${meters} m`;
  }
  return `${(meters / 1000).toFixed(1)} km`;
}

/** Extract the provider-validated local HH:MM from an ISO datetime with offset. */
export function formatTime(isoString: string): string {
  const match = /T(\d{2}:\d{2})/.exec(isoString);
  return match?.[1] ?? '--:--';
}

/** Format a local time string like "09:30" from "HH:MM" format already */
export function formatLocalTime(localTime: string): string {
  return localTime.slice(0, 5);
}

/** Decode a Google encoded polyline into lat/lng pairs */
export function decodePolyline(encoded: string): Array<{ lat: number; lng: number }> {
  const points: Array<{ lat: number; lng: number }> = [];
  let index = 0;
  let lat = 0;
  let lng = 0;

  while (index < encoded.length) {
    let shift = 0;
    let result = 0;
    let byte: number;

    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);

    lat += result & 1 ? ~(result >> 1) : result >> 1;

    shift = 0;
    result = 0;

    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);

    lng += result & 1 ? ~(result >> 1) : result >> 1;

    points.push({ lat: lat / 1e5, lng: lng / 1e5 });
  }

  return points;
}

/** Get the travel mode label */
export function travelModeLabel(mode: 'WALK' | 'DRIVE'): string {
  return mode === 'WALK' ? 'walking' : 'driving';
}

/** Get the travel leg label */
export function travelLegLabel(mode: 'WALK' | 'DRIVE'): string {
  return mode === 'WALK' ? 'Walk' : 'Drive';
}
