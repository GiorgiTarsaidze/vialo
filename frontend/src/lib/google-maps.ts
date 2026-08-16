/**
 * Central Google Maps loader and style configuration.
 * Reused by ComparisonMap and SelectionMap to avoid duplicate script loads.
 */

declare global {
  interface Window {
    google?: typeof google;
    initVialoMap?: () => void;
    gm_authFailure?: () => void;
    __vialoMapsAuthFailed?: boolean;
  }
}

export const MAPS_AUTH_FAILURE_EVENT = 'vialo:maps-auth-failure';

let loadPromise: Promise<void> | null = null;
let loadReject: ((error: Error) => void) | null = null;

function handleMapsAuthFailure(): void {
  window.__vialoMapsAuthFailed = true;
  const error = new Error('Google Maps authentication failed');
  loadReject?.(error);
  loadReject = null;
  window.dispatchEvent(new Event(MAPS_AUTH_FAILURE_EVENT));
}

function installAuthFailureHandler(): void {
  window.gm_authFailure = handleMapsAuthFailure;
}

export function loadGoogleMaps(): Promise<void> {
  installAuthFailureHandler();

  if (window.__vialoMapsAuthFailed) {
    return Promise.reject(new Error('Google Maps authentication failed'));
  }
  if (window.google?.maps) return Promise.resolve();
  if (loadPromise) return loadPromise;

  loadPromise = new Promise((resolve, reject) => {
    const key = import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY;
    if (!key) {
      reject(new Error('No Google Maps key configured'));
      return;
    }

    loadReject = reject;
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(key)}&loading=async&callback=initVialoMap`;
    script.async = true;
    script.defer = true;
    window.initVialoMap = () => {
      if (window.__vialoMapsAuthFailed) {
        reject(new Error('Google Maps authentication failed'));
        return;
      }
      loadReject = null;
      resolve();
    };
    script.onerror = () => {
      loadReject = null;
      reject(new Error('Google Maps script failed to load'));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}

/** Test and integration hook; production failures invoke window.gm_authFailure. */
export function notifyMapsAuthFailure(): void {
  handleMapsAuthFailure();
}

/** Warm Vialo palette — reduces POI clutter and matches design tokens. */
export const VIALO_MAP_STYLES: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#f4ebdd' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#e7e1f2' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#ffffff' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#e7d8d1' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#fff8ea' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'poi.park', elementType: 'geometry', stylers: [{ visibility: 'on' }, { color: '#eaf0e4' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#6d6064' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#fffcf5' }] },
];

/** Shared map options base. */
export function baseMapOptions(extraOptions?: Partial<google.maps.MapOptions>): google.maps.MapOptions {
  return {
    mapTypeControl: false,
    streetViewControl: false,
    fullscreenControl: false,
    zoomControl: true,
    gestureHandling: 'cooperative',
    styles: VIALO_MAP_STYLES,
    ...extraOptions,
  };
}
