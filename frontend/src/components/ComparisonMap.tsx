import { useEffect, useRef, useCallback, useState } from 'react';
import type { ComparisonResult, GroundedStop, GroundedPlace } from '../lib/types';
import { decodePolyline } from '../lib/format';

interface ComparisonMapProps {
  comparison: ComparisonResult;
  stops: GroundedStop[];
  origin: GroundedPlace;
}

declare global {
  interface Window {
    google?: typeof google;
    initVialoMap?: () => void;
  }
}

function loadGoogleMaps(): Promise<void> {
  if (window.google?.maps) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const existing = document.querySelector('script[src*="maps.googleapis.com"]');
    if (existing) {
      existing.addEventListener('load', () => resolve());
      return;
    }
    const key = import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY;
    if (!key) {
      reject(new Error('No Google Maps key configured'));
      return;
    }
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&callback=initVialoMap`;
    script.async = true;
    script.defer = true;
    window.initVialoMap = () => resolve();
    script.onerror = () => reject(new Error('Google Maps script failed to load'));
    document.head.appendChild(script);
  });
}

export default function ComparisonMap({ comparison, stops, origin }: ComparisonMapProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<google.maps.Map | null>(null);
  const hasRevealedRef = useRef(false);
  const [mapStatus, setMapStatus] = useState<'loading' | 'ready' | 'unavailable'>('loading');

  const prefersReducedMotion =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const drawMap = useCallback(() => {
    if (!mapRef.current || comparison.status === 'unavailable') return;
    if (!window.google?.maps) return;

    const naivePath = decodePolyline(comparison.naivePolyline);
    const optimizedPath = decodePolyline(comparison.optimizedPolyline);

    const isSameOrder = comparison.outcome === 'same_order';

    // Calculate bounds
    const bounds = new google.maps.LatLngBounds();
    naivePath.forEach((p) => bounds.extend(p));
    optimizedPath.forEach((p) => bounds.extend(p));
    stops.forEach((s) => bounds.extend({ lat: s.place.location.latitude, lng: s.place.location.longitude }));
    bounds.extend({ lat: origin.location.latitude, lng: origin.location.longitude });

    const map = new google.maps.Map(mapRef.current, {
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      zoomControl: true,
      gestureHandling: 'cooperative',
    });
    map.fitBounds(bounds, { top: 40, bottom: 40, left: 20, right: 20 });
    mapInstanceRef.current = map;

    if (isSameOrder) {
      // Single shared line
      new google.maps.Polyline({
        path: optimizedPath,
        strokeColor: '#6f3e59',
        strokeOpacity: 1,
        strokeWeight: 5,
        map,
      });
    } else if (prefersReducedMotion || hasRevealedRef.current) {
      // Show both routes immediately
      drawNaiveLine(map, naivePath);
      drawOptimizedLine(map, optimizedPath);
    } else {
      // Animated reveal
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

    // Origin marker
    new google.maps.Marker({
      position: { lat: origin.location.latitude, lng: origin.location.longitude },
      map,
      label: { text: '●', color: '#2b2326', fontSize: '10px' },
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: 10,
        fillColor: '#ffffff',
        fillOpacity: 1,
        strokeColor: '#2b2326',
        strokeWeight: 2,
      },
      title: `Origin: ${origin.displayName}`,
    });
  }, [comparison, stops, origin, prefersReducedMotion]);

  useEffect(() => {
    if (comparison.status === 'unavailable') return;
    setMapStatus('loading');
    loadGoogleMaps()
      .then(() => {
        drawMap();
        setMapStatus('ready');
      })
      .catch(() => {
        setMapStatus('unavailable');
      });
  }, [comparison, drawMap]);

  if (comparison.status === 'unavailable') {
    return null;
  }

  // Text fallback
  const isSameOrder = comparison.outcome === 'same_order';
  const textFallback = isSameOrder
    ? `Map: single optimized route with ${stops.length} numbered stops`
    : `Map: naive route (coral dashed) and optimized route (plum solid) with ${stops.length} numbered stops`;

  return (
    <div className="comparison-map-container">
      <div
        ref={mapRef}
        className="comparison-map"
        role="img"
        aria-label={textFallback}
        aria-busy={mapStatus === 'loading'}
      />
      {mapStatus === 'loading' && (
        <p className="map-status" role="status">Loading route map…</p>
      )}
      {mapStatus === 'unavailable' && (
        <p className="map-status map-status--unavailable">
          Interactive map unavailable. The verified route summary and schedule remain below.
        </p>
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
  margin-bottom: var(--space-5);
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

.map-status--unavailable {
  color: var(--color-ink);
  background: var(--color-accent-lilac);
}

.comparison-map {
  width: 100%;
  min-height: 280px;
  height: 340px;
  border-radius: var(--radius-card);
  border: 1px solid var(--color-border);
  background: var(--color-map-land);
}

@media (min-width: 768px) {
  .comparison-map {
    height: 400px;
  }
}
`;
