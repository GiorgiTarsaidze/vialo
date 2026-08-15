# Itinerary Engine Design

**Status:** Ready for implementation
**Requirements:** [`requirements.md`](requirements.md)

## 1. Architecture

```text
POST /itineraries
  -> validate request + scope + rate limit
  -> Claude structured intent and candidate stops
  -> Places grounding + split-freshness cache
  -> directed Routes matrix
  -> exact time-window solver
  -> deterministic stop dropping when required
  -> naive simulation + two ordered Compute Routes calls
  -> Maps full URL + browser-safe parts
  -> typed itinerary response + share integrity proof

POST /shares
  -> verify itinerary schema + integrity proof
  -> store computed response for 30 days

GET /shares/{shareId}
  -> application expiry check
  -> typed shared response
```

One Lambda may expose all routes behind API Gateway for the hackathon. Pipeline steps remain separate modules with external services behind interfaces.

## 2. Public endpoint contracts

### `POST /itineraries`

```ts
type PlanItineraryRequest = {
  prompt: string;
};
```

Successful responses use HTTP 200 even when a valid partial itinerary contains dropped-stop diagnostics. Request validation, rate limiting, off-topic input, provider failure, and internal failure use appropriate non-2xx statuses.

### `POST /shares`

```ts
type CreateShareRequest = {
  itinerary: ItineraryResponse;
  proof: string;
};

type CreateShareResponse = {
  shareId: string;
  shareUrl: string;
  expiresAt: string;
  deletionToken: string;
};
```

The proof envelope contains an expiry and an HMAC over the expiry plus canonical schema-versioned shareable itinerary JSON. It expires after 24 hours and is checked in constant time. This prevents arbitrary client-authored data from being published as a Vialo result without storing every prompt result.

### `GET /shares/{shareId}`

Returns the stored `ItineraryResponse` or the generic `SHARE_NOT_FOUND` response.

### `DELETE /shares/{shareId}`

Requires the creator-only deletion token in `X-Share-Delete-Token`. The token is returned only by share creation, never appears in the public URL or share read response, and is compared through a server-HMAC digest before conditional deletion.

## 3. Core types

```ts
type TravelMode = 'WALK' | 'DRIVE';
type DurationSource = 'user' | 'model_estimate';
type HoursSource = 'current' | 'regular';

type ParsedIntent = {
  localityQuery: string;
  originQuery: string;
  requestedDate: string | null;
  localStartTime: string;
  localEndTime: string;
  travelMode: TravelMode;
  returnToOrigin: boolean;
  candidates: CandidateStop[];
};

type CandidateStop = {
  candidateIndex: number;
  name: string;
  category: StopCategory;
  priority: 1 | 2 | 3;
  visitDurationMinutes: number;
  durationSource: DurationSource;
  durationEvidence?: {
    start: number;
    end: number;
    quote: string;
  };
};

type GroundedPlace = {
  placeId: string;
  displayName: string;
  formattedAddress: string;
  location: { latitude: number; longitude: number };
  primaryType?: string;
  timeZoneId: string;
  photos: PlacePhoto[];
};

type OpenInterval = {
  startEpochMs: number;
  endEpochMs: number;
  localStart: string;
  localEnd: string;
};

type GroundedStop = CandidateStop & GroundedPlace & {
  hoursSource: HoursSource;
  openIntervals: OpenInterval[];
};
```

The model schema is stricter than provider schemas. Unknown model keys are rejected. Provider responses are parsed into internal types before downstream use.

## 4. Time model

### 4.1 Timezone source

Production Places Text Search requests include `places.timeZone`. The `timeZone.id` field is an IANA zone such as `Europe/Rome` and is the authoritative schedule zone.

`utcOffsetMinutes` is deliberately excluded from scheduling. It describes only the place's current UTC offset and cannot safely represent a different date across daylight-saving changes.

### 4.2 Date resolution

1. Ground the origin and obtain its IANA timezone.
2. If Claude extracted an explicit date, validate it in that zone.
3. Otherwise resolve “today” in the origin zone at request time.
4. Require every retained stop to have the same timezone ID.
5. Build zoned instants with a pinned Temporal-compatible implementation during Phase 3.
6. Reject ambiguous or nonexistent local boundary times instead of silently selecting an offset.

### 4.3 Opening-period normalization

`normalizeOpeningHours(place, requestedDate, timeZoneId)`:

1. Record the response fetch instant and derive the seven-date `currentOpeningHours` coverage window from its local fetch date in the place timezone.
2. If the requested date is inside that window, convert every current period intersecting the date to zoned `OpenInterval` values and mark source `current`; if none intersects, return `CLOSED_ON_DATE` without consulting regular hours.
3. If the requested date is outside that window, select `regularOpeningHours.periods` by the requested local weekday and mark source `regular`.
4. Pair opening and closing endpoints chronologically, including next-date closing points and 24-hour periods.
5. Retain every usable interval for split-day schedules.
6. Return `HOURS_UNAVAILABLE` for missing or malformed data outside authoritative current coverage.

A visit is feasible only when one interval can contain its entire duration. An arrival before an interval creates a wait; an arrival after the final possible interval rejects that order.

## 5. Visit-duration model

Claude selects one fixed category and an integer duration. The Zod schema encodes the minimum and maximum from requirements. Defaults are used in the Claude prompt as guidance, not injected after an invalid response.

An out-of-range model estimate triggers one repair call containing only validation errors and the required schema. A second invalid result fails. No clamping occurs.

When Claude marks a duration as `user`, it must also return an exact character span and quote from the prompt. The backend checks the indices and quote against the in-memory prompt, parses the supported duration expression deterministically, and requires it to equal `visitDurationMinutes`. An unsupported claim is invalid model output and enters the single repair path. The evidence is stripped immediately after validation and never logged, cached, shared, or returned. The global 15–240 minute guard applies, but the category estimate range does not override a verified user value. UI metadata can therefore render `estimated` for model values and `planned` for verified user values.

## 6. Places resolution

### Request

- Endpoint: `POST https://places.googleapis.com/v1/places:searchText`
- Query: exact candidate or origin name plus locality
- `pageSize`: 5
- `languageCode`: `en`
- Field mask: required fields listed in requirements; no wildcard

### Candidate selection

1. Normalize Unicode, case, and punctuation for comparison only.
2. Prefer exact display-name matches in the intended locality.
3. Otherwise require a strong name match and address/locality compatibility.
4. Reject ambiguous top matches rather than selecting a plausible wrong place.
5. Deduplicate retained candidates by Place ID.

Photo objects retain their complete attribution arrays. The backend does not synthesize attribution or alt text.

## 7. Cache design

DynamoDB table: `place-cache`

```text
PK: PLACE#<placeId>
SK values:
  PROFILE
  HOURS#REGULAR
  HOURS#DATE#YYYY-MM-DD
```

A small query-resolution item may map a normalized query/locality hash to a Place ID:

```text
PK: QUERY#<sha256(normalizedQuery|normalizedLocality)>
SK: RESOLUTION
```

| Item | Contents | Freshness |
|---|---|---:|
| `PROFILE` | name, address, coordinates, primary type, timezone, photos | 30 days |
| `HOURS#REGULAR` | recurring periods | 7 days |
| `HOURS#DATE#...` | normalized source periods for one date | through local date end + 6 hours |
| `RESOLUTION` | query to Place ID mapping | 7 days |

Each item has `fetchedAt` and numeric `expiresAt`. Application reads reject expired items immediately; DynamoDB TTL is cleanup only. A single Places response may populate several items, but each item retains its own expiry.

Cache writes are best-effort. Cache failure does not corrupt a valid live provider result. Cached provider payloads are parsed through the same schema as live responses.

## 8. Directed matrix

Route points are indexed:

```text
0 = fixed origin
1..N = retained visit stops in candidate order
```

The max product case is ten points and 100 directed elements. The service requests all points as origins and destinations in one matrix call.

```ts
type MatrixEdge = {
  originIndex: number;
  destinationIndex: number;
  distanceMeters: number | null;
  durationSeconds: number | null;
  reachable: boolean;
};
```

The parser pre-fills every diagonal as `{ distanceMeters: 0, durationSeconds: 0, reachable: true }` because valid provider diagonal elements may omit `distanceMeters`; it initializes every off-diagonal cell as unreachable, then fills those cells only from valid provider elements. It never copies `[a][b]` to `[b][a]`.

## 9. Exact solver

### Why exhaustive permutations

The fixed origin leaves at most nine visit stops, so the upper bound is 9! = 362,880 complete orders. Each evaluation performs bounded array lookup and time-window arithmetic without network access. Exhaustive evaluation is simple to test and proves the selected order is optimal for the stated objective. A nearest-neighbor or LLM order could miss a feasible sequence or local optimum and would weaken the product claim.

Latency remains an empirical question. Phase 3 benchmarks the implementation in the Lambda-equivalent runtime. Safe branch-and-bound pruning may skip a partial order only after its accumulated travel already exceeds the current best or a hard constraint is irrecoverably violated.

### Objective

Lexicographically minimize:

1. total directed travel seconds;
2. total waiting seconds;
3. final completion epoch;
4. candidate-index sequence.

### Simulation

```text
simulate(order, activeStops, origin, matrix, window, returnToOrigin):
  cursor = window.start
  previous = origin
  entries = []

  for stop in order:
    edge = matrix[previous][stop]
    reject if unreachable
    cursor += edge.duration
    add travel entry

    interval = first interval where max(cursor, interval.start) + visit <= interval.end
    reject if none

    if cursor < interval.start:
      add wait entry
      cursor = interval.start

    arrival = cursor
    cursor += visit duration
    add stop entry(arrival, cursor, interval used)
    previous = stop

  if returnToOrigin:
    add directed return edge or reject

  reject if cursor > window.end
  return feasible schedule and objective tuple
```

The timeline arrival shown for a stop is the visit start after any wait. The preceding travel entry retains physical arrival time; the explicit wait segment explains the difference.

### Deterministic dropping

If no full-set order is feasible, rank candidate removals by:

1. priority descending (`3` first);
2. total usable opening-window seconds ascending;
3. visit duration descending;
4. candidate index descending.

Remove one stop, solve the remaining set exactly, and repeat. The diagnostic engine records the dominant factual constraint from failed simulations plus the deterministic removal reason. It does not generate prose with Claude.

## 10. Naive schedule

After the retained set is known, build naive order by filtering candidate order to retained Place IDs. Simulate it with the same directed matrix, opening intervals, duration values, start/end window, and return rule.

The naive simulation may be infeasible. It still has an ordered route geometry, but its response carries factual feasibility codes such as `VISIT_MISSES_CLOSE` or `WINDOW_OVERRUN`. The frontend uses approved templates such as “Misses 17:00 closing time.”

## 11. Real route geometry

`computeRouteMatrix` cannot return polylines. After solving, call `computeRoutes` twice:

- naive retained order;
- optimized retained order.

For each order, construct route points as `[fixedOrigin, ...orderedStops]` for an open route or `[fixedOrigin, ...orderedStops, fixedOrigin]` for a return route. Convert that sequence mechanically: first point is `origin`, last point is `destination`, and interior points are `intermediates`. Therefore an open route's literal destination changes when its final ordered stop changes, while the terminal rule remains identical; a return route always ends at the fixed origin. A one-stop open route has no intermediates.

Each call uses:

```json
{
  "origin": "first route point",
  "intermediates": "all interior route points in caller order",
  "destination": "last route point",
  "travelMode": "same mode",
  "departureTime": "same policy and value",
  "routeModifiers": "same options",
  "computeAlternativeRoutes": false,
  "optimizeWaypointOrder": false,
  "polylineQuality": "HIGH_QUALITY",
  "polylineEncoding": "ENCODED_POLYLINE"
}
```

Field mask:

```text
routes.distanceMeters,
routes.duration,
routes.polyline.encodedPolyline,
routes.legs.distanceMeters,
routes.legs.duration
```

At the nine-stop cap, requests remain below the documented 25-intermediate limit. Route and leg `duration` strings use the same strict protobuf-duration parser as matrix values (for example, `"518s"`). The response's route totals power the comparison metrics; encoded polylines power the shared-bounds overlay. If either response is unavailable, return `comparison.status = 'unavailable'` and do not draw a substitute.

If naive and optimized sequences are identical, return `same_order`, zero deltas, and one shared geometry for rendering even though both ordered calls remain independently evidenced. A one-stop result uses the more specific copy outcome `no_reordering_needed`. Otherwise compute signed deltas from the real route totals. Never clamp an unfavorable delta: if it contradicts the directed-matrix objective, retain the real values, emit `METRICS_DIVERGED`, and present the result as schedule-aware rather than claiming travel savings.

## 12. Maps handoff

Build the full cross-platform URL using `URL` and `URLSearchParams`, `api=1`, ordered origin/destination/waypoint labels, matching place-ID parameters, and `travelmode=walking|driving`.

The full URL is valid only when:

- every place-ID list aligns with its text/coordinate list;
- intermediate count is at most nine;
- encoded length is at most 2,048 characters.

For mobile-browser compatibility, also partition route points into overlapping parts that contain at most five points each: origin, up to three intermediates, destination. The destination of one part becomes the origin of the next. Every part receives the same encoding and length checks.

```ts
type MapsHandoff = {
  fullRouteUrl: string | null;
  fullRouteUniversallySupported: boolean;
  browserSafeParts: Array<{
    part: number;
    totalParts: number;
    startStopIndex: number;
    endStopIndex: number;
    url: string;
  }>;
  warningCode?: 'MOBILE_WAYPOINT_LIMIT' | 'FULL_URL_TOO_LONG';
  errorCode?: 'HANDOFF_UNAVAILABLE';
};
```

No part uses decorative labels such as “morning” unless those boundaries exist in the schedule.

## 13. Sharing

The itinerary response contains a 24-hour proof envelope over canonical shareable JSON. Canonicalization strips `requestId`, diagnostics that contain transient correlation data, and the proof itself. `POST /shares` verifies the expiry and HMAC in constant time, then uses a transaction and proof digest as an idempotency claim so retries return the same share rather than creating duplicates. It generates a random deletion token and stores only `HMAC(shareDeletionSecret, deletionToken)`:

```text
PK: SHARE#<randomId>
response: schema-versioned computed itinerary
deleteTokenDigest: server-HMAC digest
proofDigest: idempotency key
createdAt: ISO timestamp
expiresAt: epoch seconds, now + 30 days
```

The raw deletion token is returned exactly once and kept separate from the public share URL. `DELETE` compares its digest in constant time before conditional deletion; a viewer with only the URL cannot delete. The original prompt, IP hash, duration evidence, raw provider responses, and raw Claude output are never included. Reads enforce `expiresAt` even before DynamoDB TTL deletion.

## 14. Rate limiting

DynamoDB table: `request-limits`

```text
PK: LIMIT#<HMAC(serverSalt, canonicalIp)>
SK: HOUR#<UTC hour bucket>
count: atomic integer
expiresAt: bucket end + 1 hour
```

An atomic conditional update permits counts 1–5 and rejects later requests. The salt is a server secret. Logs contain neither the canonical IP nor its full hash.

## 15. Response model

```ts
type ItineraryResponse = {
  schemaVersion: 1;
  requestId: string;
  status: 'complete' | 'partial';
  locality: { name: string; timeZoneId: string; date: string };
  travelMode: TravelMode;
  window: { start: string; end: string };
  origin: GroundedPlace;
  stops: ItineraryStop[];
  timeline: Array<TravelEntry | WaitEntry | VisitEntry>;
  droppedStops: DroppedStop[];
  comparison: RouteComparison | { status: 'unavailable'; diagnostic: Diagnostic };
  mapsHandoff: MapsHandoff;
  totals: {
    visitSeconds: number;
    travelSeconds: number;
    waitSeconds: number;
    elapsedSeconds: number;
  };
  diagnostics: Diagnostic[];
  shareProof: {
    expiresAt: string;
    hmac: string;
  };
};
```

User-facing text is rendered from diagnostic codes and typed parameters in the frontend, not provider or model prose.

## 16. Failure mapping

| Failure | HTTP | Result |
|---|---:|---|
| invalid/off-topic | 400/422 | typed error, no paid calls after guard |
| rate limit | 429 | retry timestamp |
| origin failure | 422 | no itinerary |
| candidate grounding/hours failure | 200 | partial diagnostics when other stops remain |
| provider outage before schedule | 502 | retryable typed error |
| no feasible retained stop | 422 | `NO_FEASIBLE_ITINERARY` with diagnostics |
| geometry outage | 200 | schedule retained, comparison unavailable |
| Maps URL limit | 200 | valid parts or handoff unavailable |
| expired share | 404 | generic share-not-found state |
| invalid share deletion token | 404 | same generic share-not-found state |

## 17. Security, privacy, and observability

- Zod validates requests, Claude output, provider responses, cache data, shares, and final responses.
- React receives no raw model prose or provider errors.
- Secrets remain environment-only.
- Raw prompts are processed in memory and excluded from structured logs and shares.
- Logs record stage name, durations, counts, cache hit/miss, matrix size, permutations, and stable failure code.
- CloudWatch retention is configured explicitly in infrastructure rather than left indefinite.
- Provider retries are bounded to two retry attempts with exponential backoff and jitter for retryable errors only.
- A request-level timeout budget leaves time to return a typed error before Lambda termination.

## 18. Test design

### Unit tests

- category bounds and duration provenance
- local date defaulting and DST rejection
- current-to-regular opening-hours fallback
- split intervals, overnight intervals, 24-hour and closed dates
- expired cache items despite delayed DynamoDB TTL deletion
- directed asymmetric matrix
- exact order, wait insertion, tie-breaks, return leg
- deterministic dropping and diagnostics
- full and segmented Maps URLs
- share proof, idempotency, creator-only deletion, and expiry
- prompt/IP omission from logs and share writes

### Integration tests

- Places adapter reads canonical fixtures and tolerates the old fixture's missing `timeZone` only when the test supplies a typed augmentation; production parsing requires it.
- Routes matrix adapter preserves 518s and 508s directed values.
- `computeRoutes` adapter uses a dedicated recorded geometry fixture captured during Phase 3; no fake polyline is accepted as production evidence.
- External HTTP is mocked at adapter boundaries.

### Benchmark

Run 8! and 9! representative schedules in a Lambda-equivalent Node runtime at the configured memory. Record median and p95 after warm-up in `DEVLOG.md`. Optimize only if evidence requires it, preserving exactness.

## 19. Rejected alternatives

- **Nearest-neighbor or LLM ordering:** not provably optimal and can miss time-window feasibility.
- **Using `utcOffsetMinutes`:** current-offset field cannot represent the requested date reliably.
- **Time Zone API:** unnecessary because Places now returns an IANA `timeZone.id` in the same grounding response.
- **Mirroring the matrix:** invalidated by the real directed fixture.
- **Straight-line map overlays:** not route evidence.
- **Assuming missing hours mean open:** violates evidence and can send users to a closed place.
- **Automatically storing every result:** unnecessary data retention; sharing is explicit.
- **Silently shortening the Maps URL:** changes the solved itinerary.
