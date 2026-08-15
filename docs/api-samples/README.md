# Google Maps API validation fixtures

These files are sanitized raw responses captured from live Google Maps Platform calls on 2026-08-13 and 2026-08-15. They contain no request headers or API keys.

They serve two purposes:

1. Integration-test fixtures for parsing and scheduling behavior.
2. Public evidence that Vialo's API integration was validated against real responses rather than invented schemas.

## `places-san-marco.json`

Source: Places API (New), Text Search for Saint Mark's Basilica in Venice.

Validated observations:

- One stable place ID, formatted address, and coordinate pair
- Seven recurring `regularOpeningHours` periods
- Seven date-specific `currentOpeningHours` periods
- Ten photo records with author attribution
- No typical-visit-duration field

When a fixture photo is used in tests or product UI, preserve the API-provided author attribution. The fixture itself is test data; it is not a license to redistribute the referenced image bytes.

## `routes-venice-walk.json`

Source: Routes API `computeRouteMatrix`, walking mode, for two Venice coordinates.

Validated observations:

- Four route-matrix elements
- Two zero-duration diagonal elements
- A 592-meter route in each direction
- Directed durations of 518 seconds and 508 seconds

The unequal reverse durations are intentional evidence that route matrices must not be treated as symmetric.

## `routes-venice-geometry.json`

Source: Routes API `computeRoutes`, walking mode, for an ordered three-point Venice route captured on 2026-08-15.

Validated observations:

- One real encoded high-quality polyline
- Two ordered route legs
- A 1,526-meter route with a provider duration of 1,286 seconds
- The live API rejects `routingPreference` for walking requests, so Vialo omits it for `WALK` and uses `TRAFFIC_UNAWARE` only for `DRIVE`

The fixture is parser and request-shape evidence only. Production always calls Routes for the user's grounded stops and never returns this fixture as fallback geometry.
