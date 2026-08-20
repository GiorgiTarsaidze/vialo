/**
 * Polyline options for the naive-vs-optimized comparison map.
 *
 * Kept as pure option builders so the visual contract is unit-testable without
 * a Maps runtime. Two rules come from the design system:
 *
 * 1. The optimized route is heavier and fully opaque, so it reads as the answer.
 * 2. The naive baseline must stay legible enough to verify the comparison. Both
 *    orders often share the same streets, so the thin dashed baseline is drawn
 *    ABOVE the solid optimized line — otherwise a 5 px solid stroke hides it
 *    completely and the comparison looks like a single route.
 *
 * Colour is never the only distinction: solid versus dashed, and different
 * stroke weights, carry the difference too, and both lines are also labelled.
 */

export const NAIVE_STROKE = '#a95242';
export const OPTIMIZED_STROKE = '#6f3e59';

/** The baseline sits above the optimized line so overlapping segments stay visible. */
export const NAIVE_Z_INDEX = 3;
export const OPTIMIZED_Z_INDEX = 2;

export interface MapPoint {
  lat: number;
  lng: number;
}

/**
 * Coral dashed baseline. The base stroke is transparent and the dashes are
 * drawn as repeated symbols, which is the documented way to render a dashed
 * polyline in the Maps JavaScript API.
 */
export function naiveLineOptions(path: MapPoint[]): Record<string, unknown> {
  return {
    path,
    strokeColor: NAIVE_STROKE,
    strokeOpacity: 0,
    strokeWeight: 3,
    geodesic: true,
    zIndex: NAIVE_Z_INDEX,
    icons: [
      {
        icon: {
          path: 'M 0,-1 0,1',
          strokeColor: NAIVE_STROKE,
          strokeOpacity: 0.95,
          strokeWeight: 3,
          scale: 3,
        },
        offset: '0',
        repeat: '16px',
      },
    ],
  };
}

/** Plum solid optimized route: heavier, fully opaque, drawn underneath. */
export function optimizedLineOptions(path: MapPoint[]): Record<string, unknown> {
  return {
    path,
    strokeColor: OPTIMIZED_STROKE,
    strokeOpacity: 1,
    strokeWeight: 5,
    geodesic: true,
    zIndex: OPTIMIZED_Z_INDEX,
  };
}
