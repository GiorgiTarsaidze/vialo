import { useEffect, useRef, useCallback, useState } from 'react';
import type { ComparisonResult, GroundedStop, GroundedPlace } from '../lib/types';
import { decodePolyline } from '../lib/format';
import {
  MAPS_AUTH_FAILURE_EVENT,
  baseMapOptions,
  loadGoogleMaps,
} from '../lib/google-maps';

interface ComparisonMapProps {
  comparison: ComparisonResult;
  stops: GroundedStop[];
  origin: GroundedPlace;
  destination?: GroundedPlace | null;
}

export default function ComparisonMap({ comparison, stops, origin, destination }: ComparisonMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const hasRevealedRef = useRef(false);
  const [mapStatus, setMapStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading');
  const authFailedRef = useRef(false);

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const drawMap = useCallback(() => {
    if (!mapRef.current || comparison.status === 'unavailable') return;
    if (!window.google?.maps) return;
    if (authFailedRef.current) return;

    const naivePath = decodePolyline(comparison.naivePolyline);
    const optimizedPath = decodePolyline(comparison.optimizedPolyline);

    const isSameOrder = comparison.outcome === 'same_order';

    // Calculate bounds
    const bounds = new google.maps.LatLngBounds();
    naivePath.forEach((p) => bounds.extend(p));
    optimizedPath.forEach((p) => bounds.extend(p));
    stops.forEach((s) => bounds.extend({ lat: s.place.location.latitude, lng: s.place.location.longitude }));
    bounds.extend({ lat: origin.location.latitude, lng: origin.location.longitude });
    if (destination) {
      bounds.extend({ lat: destination.location.latitude, lng: destination.location.longitude });
    }

    const map = new google.maps.Map(mapRef.current, baseMapOptions());
    map.fitBounds(bounds, { top: 40, bottom: 40, left: 20, right: 20 });
    mapInstanceRef.current = map;

    if (isSameOrder) {
      new google.maps.Polyline({
        path: optimizedPath,
        strokeColor: '#6f3e59',
        strokeOpacity: 1,
        strokeWeight: 5,
        map,
      });
    } else if (prefersReducedMotion || hasRevealedRef.current) {
      drawNaiveLine(map, naivePath);
      drawOptimizedLine(map, optimizedPath);
    } else {
      hasRevealedRef.current = true;
      const naiveLine = drawNaiveLine(map, naivePath);
      const optLine = drawOptimizedLine(map, optimizedPath);
      naiveLine.setMap(null);
      optLine.setMap(null);
      setTimeout(() => naiveLine.setMap(map), 0);
      setTimeout(() => optLine.setMap(map), 350);
    }

    // Numbered markers for stops (optimized order)
    const optimizedOrder = comparison.optimized.stopOrder;
    optimizedOrder.forEach((candidateIdx, seqIdx) => {
      const stop = stops.find((s) => s.candidateIndex === candidateIdx);
      if (!stop) return;
      new google.maps.Marker({
        position: { lat: stop.place.location.latitude, lng: stop.place.location.longitude },
        map,
        label: {
          text: String(seqIdx + 1),
          color: '#ffffff',
          fontSize: '12px',
          fontWeight: '600',
        },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 14,
          fillColor: '#6f3e59',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
        title: `${seqIdx + 1}. ${stop.name}`,
        zIndex: 10 + seqIdx,
      });
    });

    // Origin/start marker
    const sameStartEnd =
      destination &&
      origin.placeId === destination.placeId;

    new google.maps.Marker({
      position: { lat: origin.location.latitude, lng: origin.location.longitude },
      map,
      label: {
        text: sameStartEnd ? 'S/E' : 'S',
        color: '#2b2326',
        fontSize: '10px',
        fontWeight: '600',
      },
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 11,
        fillColor: '#ffffff',
        fillOpacity: 1,
        strokeColor: '#2b2326',
        strokeWeight: 2,
      },
      title: sameStartEnd
        ? `Start & End: ${origin.displayName}`
        : `Start: ${origin.displayName}`,
    });

    // Destination marker (distinct from start)
    if (destination && !sameStartEnd) {
      new google.maps.Marker({
        position: { lat: destination.location.latitude, lng: destination.location.longitude },
        map,
        label: { text: 'E', color: '#ffffff', fontSize: '10px', fontWeight: '600' },
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 11,
          fillColor: '#6f3e59',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
        title: `End: ${destination.displayName}`,
      });
    }
  }, [comparison, stops, origin, destination, prefersReducedMotion]);

  useEffect(() => {
    if (comparison.status === 'unavailable') return;

    const handleAuthFailure = () => {
      authFailedRef.current = true;
      if (mapRef.current) mapRef.current.replaceChildren();
      setMapStatus('unavailable');
    };
    window.addEventListener(MAPS_AUTH_FAILURE_EVENT, handleAuthFailure);

    setMapStatus('loading');
    loadGoogleMaps()
      .then(() => {
        if (authFailedRef.current) {
          setMapStatus('unavailable');
          return;
        }
        drawMap();
        setMapStatus('ready');
      })
      .catch(() => {
        setMapStatus('unavailable');
      });

    return () => {
      window.removeEventListener(MAPS_AUTH_FAILURE_EVENT, handleAuthFailure);
    };
  }, [comparison, drawMap]);

  if (comparison.status === 'unavailable') {
    return null;
  }

  const isSameOrder = comparison.outcome === 'same_order';
  const destinationLabel = destination
    ? ` ending at ${destination.displayName}`
    : '';
  const textFallback = isSameOrder
    ? `Map: single optimized route with ${stops.length} numbered stops${destinationLabel}`
    : `Map: naive route (coral dashed) and optimized route (plum solid) with ${stops.length} numbered stops${destinationLabel}`;

  return (
    <div className="comparison-map-container">
      {mapStatus !== 'unavailable' && (
        <div
          ref={mapRef}
          className="comparison-map"
          role="img"
          aria-label={textFallback}
          aria-busy={mapStatus === 'loading'}
        />
      )}
      {mapStatus === 'loading' && (
        <p className="map-status" role="status">Loading route map…</p>
      )}
      {mapStatus === 'unavailable' && (
        <div className="map-fallback">
          <p className="map-status map-status--unavailable">
            Interactive map unavailable. The verified route summary and schedule remain below.
          </p>
        </div>
      )}

      {/* Outside legend */}
      {mapStatus === 'ready' && !isSameOrder && (
        <div className="map-legend" aria-label="Route legend">
          <span className="legend-item">
            <span className="legend-line legend-line--naive" aria-hidden="true" />
            <span className="legend-text">Naive order</span>
          </span>
          <span className="legend-item">
            <span className="legend-line legend-line--optimized" aria-hidden="true" />
            <span className="legend-text">Vialo order</span>
          </span>
          <span className="legend-item">
            <span className="legend-marker legend-marker--start" aria-hidden="true">S</span>
            <span className="legend-text">Start</span>
          </span>
          {destination && origin.placeId !== destination.placeId && (
            <span className="legend-item">
              <span className="legend-marker legend-marker--end" aria-hidden="true">E</span>
              <span className="legend-text">End</span>
            </span>
          )}
        </div>
      )}

      {/* Accessible text alternative */}
      <div className="sr-only">
        {textFallback}. Stop order:{' '}
        {comparison.optimized.stopOrder.map((idx, i) => {
          const stop = stops.find((s) => s.candidateIndex === idx);
          return `${i + 1}. ${stop?.name ?? 'Unknown'}`;
        }).join(', ')}
      </div>
      <style>{styles}</style>
    </div>
  );
}

function drawNaiveLine(map: google.maps.Map, path: Array<{ lat: number; lng: number }>): google.maps.Polyline {
  return new google.maps.Polyline({
    path,
    strokeColor: '#a95242',
    strokeOpacity: 0.62,
    strokeWeight: 3,
    geodesic: true,
    icons: [{
      icon: { path: 'M 0,-1 0,1', strokeOpacity: 1, scale: 3 },
      offset: '0',
      repeat: '20px',
    }],
    map,
  });
}

function drawOptimizedLine(map: google.maps.Map, path: Array<{ lat: number; lng: number }>): google.maps.Polyline {
  return new google.maps.Polyline({
    path,
    strokeColor: '#6f3e59',
    strokeOpacity: 1,
    strokeWeight: 5,
    geodesic: true,
    map,
  });
}

const styles = `
.comparison-map-container {
  position: relative;
  overflow: hidden;
}

.map-status {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  padding: var(--space-5);
  border-radius: var(--radius-card);
  color: var(--color-ink-muted);
  background: var(--color-map-land);
  text-align: center;
  pointer-events: none;
}

.map-fallback {
  position: relative;
}

.map-status--unavailable {
  position: relative;
  color: var(--color-ink);
  background: var(--color-accent-lilac);
  padding: var(--space-5);
  border-radius: var(--radius-card);
  pointer-events: auto;
}

.comparison-map {
  width: 100%;
  min-height: 280px;
  height: 300px;
  border-radius: var(--radius-card);
  border: 1px solid var(--color-border);
  background: var(--color-map-land);
  overflow: hidden;
}

@media (min-width: 768px) {
  .comparison-map {
    height: 380px;
  }
}

.map-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  padding: var(--space-3) 0;
  margin-top: var(--space-2);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.legend-line {
  width: 24px;
  height: 3px;
  border-radius: 2px;
  flex-shrink: 0;
}

.legend-line--naive {
  background: repeating-linear-gradient(
    90deg,
    var(--color-naive) 0px,
    var(--color-naive) 8px,
    transparent 8px,
    transparent 14px
  );
  opacity: 0.7;
}

.legend-line--optimized {
  background: var(--color-optimized);
  height: 4px;
}

.legend-marker--start {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--color-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 600;
  color: var(--color-ink);
  flex-shrink: 0;
}

.legend-marker--end {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 600;
  color: #ffffff;
  flex-shrink: 0;
}

.legend-text {
  font-size: 12px;
  color: var(--color-ink-muted);
  font-weight: 500;
}
`;
