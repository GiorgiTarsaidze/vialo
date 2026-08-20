import { useEffect, useRef, useState } from 'react';
import type { PlaceRef } from '../lib/types';
import { buildMarkerSvg } from '../lib/marker-helpers';
import { useFullscreen } from '../hooks/use-fullscreen';
import {
  MAPS_AUTH_FAILURE_EVENT,
  baseMapOptions,
  loadGoogleMaps,
} from '../lib/google-maps';

interface SelectionMapProps {
  origin: PlaceRef | null;
  destination: PlaceRef | null;
}

/** Compute marker data from origin/destination without any Maps dependency */
export function getMarkerData(origin: PlaceRef | null, destination: PlaceRef | null) {
  const markers: Array<{
    lat: number;
    lng: number;
    label: string;
    title: string;
    fillColor: string;
    type: 'start' | 'end' | 'same';
  }> = [];

  if (!origin?.location && !destination?.location) return markers;

  const samePlace =
    origin?.location &&
    destination?.location &&
    origin.placeId === destination.placeId;

  if (samePlace && origin.location) {
    markers.push({
      lat: origin.location.latitude,
      lng: origin.location.longitude,
      label: 'S/E',
      title: `Start & End: ${origin.displayName}`,
      fillColor: '#6f3e59',
      type: 'same',
    });
  } else {
    if (origin?.location) {
      markers.push({
        lat: origin.location.latitude,
        lng: origin.location.longitude,
        label: 'S',
        title: `Start: ${origin.displayName}`,
        fillColor: '#2b2326',
        type: 'start',
      });
    }
    if (destination?.location) {
      markers.push({
        lat: destination.location.latitude,
        lng: destination.location.longitude,
        label: 'E',
        title: `End: ${destination.displayName}`,
        fillColor: '#6f3e59',
        type: 'end',
      });
    }
  }

  return markers;
}

/**
 * A small subordinate map that shows selected start/end markers.
 * Uses locations returned by autocomplete. No google.maps.places/PlacesService.
 */
export default function SelectionMap({ origin, destination }: SelectionMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const [status, setStatus] = useState<'hidden' | 'loading' | 'ready' | 'error'>('hidden');

  const markers = getMarkerData(origin, destination);
  const hasAny = markers.length > 0;

  const refitBounds = () => {
    const map = mapInstanceRef.current;
    if (!map || !markers.length) return;
    if (markers.length === 1) {
      map.setCenter({ lat: markers[0]!.lat, lng: markers[0]!.lng });
      map.setZoom(14);
    } else {
      const bounds = new google.maps.LatLngBounds();
      markers.forEach((m) => bounds.extend({ lat: m.lat, lng: m.lng }));
      map.fitBounds(bounds, { top: 30, bottom: 30, left: 20, right: 20 });
    }
  };

  const { isFullscreen, containerRef, triggerRef, toggleFullscreen } = useFullscreen({
    onResize: refitBounds,
  });

  useEffect(() => {
    const handleAuthFailure = () => {
      if (mapRef.current) mapRef.current.replaceChildren();
      setStatus('error');
    };
    window.addEventListener(MAPS_AUTH_FAILURE_EVENT, handleAuthFailure);
    return () => window.removeEventListener(MAPS_AUTH_FAILURE_EVENT, handleAuthFailure);
  }, []);

  useEffect(() => {
    if (!hasAny) {
      setStatus('hidden');
      return;
    }
    if (status === 'ready' || status === 'loading') return;
    setStatus('loading');
    loadGoogleMaps()
      .then(() => setStatus('ready'))
      .catch(() => setStatus('error'));
  }, [hasAny, status]);

  useEffect(() => {
    if (status !== 'ready' || !mapRef.current || !window.google?.maps) return;

    if (!mapInstanceRef.current) {
      mapInstanceRef.current = new google.maps.Map(mapRef.current, baseMapOptions({
        zoom: 13,
        center: { lat: 41.7, lng: 44.8 },
      }));
    }

    const map = mapInstanceRef.current;

    // Clear old markers
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];

    if (markers.length === 0) return;

    const bounds = new google.maps.LatLngBounds();

    for (const m of markers) {
      const pos = { lat: m.lat, lng: m.lng };
      const markerType = m.type === 'same' ? 'origin-destination' : m.type === 'start' ? 'origin' : 'destination';
      const iconUrl = buildMarkerSvg(0, 'other', markerType);

      const marker = new google.maps.Marker({
        position: pos,
        map,
        icon: {
          url: iconUrl,
          scaledSize: new google.maps.Size(36, 36),
          anchor: new google.maps.Point(18, 18),
        },
        title: m.title,
      });
      markersRef.current.push(marker);
      bounds.extend(pos);
    }

    if (markers.length === 1) {
      map.setCenter({ lat: markers[0]!.lat, lng: markers[0]!.lng });
      map.setZoom(14);
    } else {
      map.fitBounds(bounds, { top: 30, bottom: 30, left: 20, right: 20 });
    }
  }, [status, markers]);

  if (!hasAny) {
    // Fallback: show location-unavailable note if origin is selected but has no coords
    if ((origin && !origin.location) || (destination && !destination.location)) {
      return (
        <div className="selection-map-container" aria-hidden="true">
          <div className="selection-map selection-map--placeholder">
            <span className="selection-map-loading">Map preview requires location data</span>
          </div>
          <style>{styles}</style>
        </div>
      );
    }
    return null;
  }

  return (
    <div
      ref={containerRef}
      className={`selection-map-container ${isFullscreen ? 'selection-map-container--fullscreen' : ''}`}
      role="group"
      aria-label="Selected locations map"
    >
      {status === 'ready' && (
        <>
          <div ref={mapRef} className="selection-map" />
          <button
            ref={triggerRef}
            type="button"
            className="selection-map-fullscreen-btn"
            onClick={toggleFullscreen}
            aria-label={isFullscreen ? 'Exit full screen' : 'View map full screen'}
            title={isFullscreen ? 'Exit full screen' : 'Full screen'}
          >
            {isFullscreen ? (
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                <path d="M6 2v4H2M12 2v4h4M6 16v-4H2M12 16v-4h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 18 18" fill="none" aria-hidden="true">
                <path d="M2 6V2h4M16 6V2h-4M2 12v4h4M16 12v4h-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            )}
          </button>
        </>
      )}
      {status === 'loading' && (
        <div className="selection-map selection-map--placeholder">
          <span className="selection-map-loading">Loading map…</span>
        </div>
      )}
      {status === 'error' && (
        <div className="selection-map selection-map--placeholder">
          <span className="selection-map-loading">Map preview unavailable</span>
        </div>
      )}
      <style>{styles}</style>
    </div>
  );
}

const styles = `
.selection-map-container {
  position: relative;
  margin-top: var(--space-4);
  border-radius: var(--radius-card);
  overflow: hidden;
  border: 1px solid var(--color-border);
}

.selection-map-container--fullscreen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  border-radius: 0;
  border: none;
  margin: 0;
  background: var(--color-canvas);
}

.selection-map-container--fullscreen .selection-map {
  height: 100vh;
}

.selection-map {
  width: 100%;
  height: 160px;
  background: var(--color-map-land);
}

.selection-map--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
}

.selection-map-loading {
  font-size: 13px;
  color: var(--color-ink-muted);
}

.selection-map-fullscreen-btn {
  position: absolute;
  top: var(--space-2);
  right: var(--space-2);
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface-strong);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  color: var(--color-ink);
  box-shadow: 0 1px 4px rgb(43 35 38 / 0.08);
  cursor: pointer;
  z-index: 10;
  transition: background var(--duration-fast) ease;
}

.selection-map-fullscreen-btn:hover {
  background: var(--color-primary-soft);
}

.selection-map-fullscreen-btn:focus-visible {
  outline: 2px solid var(--color-focus);
  outline-offset: 2px;
}
`;
