/**
 * Vialo API contract types — mirrors backend Pydantic camelCase aliases.
 * These are runtime-validated via guard functions in guards.ts.
 */

// --- Enums and literals ---

export type TravelMode = 'WALK' | 'DRIVE';
export type DurationSource = 'user' | 'model_estimate';
export type HoursSource = 'current' | 'regular';
export type StopCategory =
  | 'quick_viewpoint'
  | 'landmark'
  | 'museum_gallery'
  | 'historic_religious_site'
  | 'neighborhood_market_park'
  | 'food_break'
  | 'experience_tour'
  | 'other';

export type DiagnosticCode =
  | 'INVALID_INPUT'
  | 'INVALID_DATE'
  | 'INVALID_TIME_WINDOW'
  | 'OFF_TOPIC'
  | 'RATE_LIMITED'
  | 'MODEL_OUTPUT_INVALID'
  | 'ORIGIN_NOT_FOUND'
  | 'PLACE_NOT_FOUND'
  | 'DUPLICATE_PLACE'
  | 'OUTSIDE_LOCALITY'
  | 'HOURS_UNAVAILABLE'
  | 'CLOSED_ON_DATE'
  | 'LOCAL_TIME_AMBIGUOUS'
  | 'ROUTE_NOT_FOUND'
  | 'NO_REACHABLE_STOPS'
  | 'NO_FEASIBLE_ITINERARY'
  | 'COMPARISON_UNAVAILABLE'
  | 'METRICS_DIVERGED'
  | 'HANDOFF_UNAVAILABLE'
  | 'SHARE_NOT_FOUND'
  | 'PROVIDER_UNAVAILABLE'
  | 'AI_BUDGET_EXCEEDED'
  | 'INTERNAL_ERROR'
  | 'WALKING_ROUTES_BETA'
  | 'GROUNDING_EXCLUSION';

// --- Sub-types ---

export interface Location {
  latitude: number;
  longitude: number;
}

export interface PhotoAttribution {
  displayName: string;
  uri: string;
  photoUri: string | null;
}

export interface PlacePhoto {
  name: string;
  widthPx: number;
  heightPx: number;
  authorAttributions: PhotoAttribution[];
}

export interface GroundedPlace {
  placeId: string;
  displayName: string;
  formattedAddress: string;
  location: Location;
  primaryType: string | null;
  timeZoneId: string;
  photos: PlacePhoto[];
}

export interface OpenInterval {
  start: string;
  end: string;
  localStart: string;
  localEnd: string;
}

export interface GroundedStop {
  candidateIndex: number;
  name: string;
  category: StopCategory;
  priority: number;
  visitDurationMinutes: number;
  durationSource: DurationSource;
  place: GroundedPlace;
  hoursSource: HoursSource;
  openIntervals: OpenInterval[];
}

// --- Timeline entries ---

export interface TravelEntry {
  type: 'travel';
  fromIndex: number;
  toIndex: number;
  mode: TravelMode;
  durationSeconds: number;
  distanceMeters: number;
  departure: string;
  arrival: string;
}

export interface WaitEntry {
  type: 'wait';
  stopIndex: number;
  durationSeconds: number;
  waitStart: string;
  waitEnd: string;
  reason: string;
}

export interface VisitEntry {
  type: 'visit';
  stopIndex: number;
  arrival: string;
  departure: string;
  durationMinutes: number;
  intervalUsed: OpenInterval;
}

export type TimelineEntry = TravelEntry | WaitEntry | VisitEntry;

// --- Route comparison ---

export interface RouteMetrics {
  totalDistanceMeters: number;
  totalDurationSeconds: number;
  stopOrder: number[];
}

export interface RouteComparison {
  status: 'available';
  naive: RouteMetrics;
  optimized: RouteMetrics;
  naivePolyline: string;
  optimizedPolyline: string;
  distanceDeltaMeters: number;
  durationDeltaSeconds: number;
  naiveFeasible: boolean;
  naiveInfeasibilityCodes: string[];
  outcome: 'improved' | 'same_order' | 'no_reordering_needed' | 'metrics_diverged';
}

export interface ComparisonUnavailable {
  status: 'unavailable';
  reasonCode: string;
}

export type ComparisonResult = RouteComparison | ComparisonUnavailable;

// --- Maps handoff ---

export interface MapsHandoffPart {
  part: number;
  totalParts: number;
  startStopIndex: number;
  endStopIndex: number;
  url: string;
}

export interface MapsHandoff {
  fullRouteUrl: string | null;
  fullRouteUniversallySupported: boolean;
  browserSafeParts: MapsHandoffPart[];
  warningCode: 'MOBILE_WAYPOINT_LIMIT' | 'FULL_URL_TOO_LONG' | null;
  errorCode: 'HANDOFF_UNAVAILABLE' | null;
}

// --- Diagnostics ---

export interface Diagnostic {
  code: DiagnosticCode;
  message: string;
  stopName: string | null;
  candidateIndex: number | null;
  detail: Record<string, string | number | boolean> | null;
}

export interface DroppedStop {
  candidateIndex: number;
  name: string;
  reasonCode: DiagnosticCode;
  reasonDetail: string;
}

// --- Top-level response ---

export interface TimeWindow {
  start: string;
  end: string;
  localStart: string;
  localEnd: string;
  date: string;
}

export interface Locality {
  name: string;
  timeZoneId: string;
}

export interface Totals {
  visitSeconds: number;
  travelSeconds: number;
  waitSeconds: number;
  elapsedSeconds: number;
}

export interface ShareProof {
  expiresAt: string;
  hmac: string;
}

export interface ItineraryResponse {
  schemaVersion: 1;
  requestId: string;
  status: 'complete' | 'partial';
  locality: Locality;
  travelMode: TravelMode;
  window: TimeWindow;
  origin: GroundedPlace;
  stops: GroundedStop[];
  timeline: TimelineEntry[];
  droppedStops: DroppedStop[];
  comparison: ComparisonResult;
  mapsHandoff: MapsHandoff;
  totals: Totals;
  diagnostics: Diagnostic[];
  shareProof: ShareProof | null;
}

// --- Share API ---

export interface CreateShareResponse {
  shareId: string;
  shareUrl: string;
  deletionToken: string;
}

// --- Error response ---

export interface ApiError {
  error: {
    code: string;
    message: string;
  };
}
