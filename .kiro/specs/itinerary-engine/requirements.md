# Itinerary Engine Requirements

**Status:** Ready for implementation
**Scope:** Backend only
**Product cap:** One local-calendar day, one city, one fixed origin, and up to nine visit stops

## Purpose

The itinerary engine turns one bounded natural-language request into a grounded, feasible schedule. It uses Claude only for typed intent and candidate selection, Google Places for place facts, Google Routes for directed travel data and real geometry, and deterministic code for every scheduling decision.

The engine must never invent a place, opening interval, route, visit duration provenance, or handoff result.

## Non-goals

- Multi-day planning
- Transit, cycling, reservations, ticket inventory, or pricing
- User accounts or profiles
- LLM-written prose displayed to users
- Heuristic route ordering at the current product cap
- Treating a matrix edge, straight line, or fixture as route geometry

## Terms

- **Origin:** Fixed start point; not counted as a visit stop.
- **Candidate order:** Claude's typed stop order before route optimization.
- **Naive order:** Candidate order restricted to the exact retained stop set used by the optimized result.
- **Grounded stop:** Candidate resolved to a Places ID and required structured fields.
- **Requested date:** Calendar date interpreted in the itinerary's IANA timezone.
- **Current hours:** Date-specific `currentOpeningHours` periods that explicitly contain the requested date.
- **Regular hours:** Recurring `regularOpeningHours` periods used only when current hours do not cover the requested date.
- **Feasible:** Every travel, wait, and visit segment fits the user window and every visit fits wholly inside an opening interval.

## Requirement 1 — Request validation and scope guard

1.1. WHEN a request reaches the backend, THE SYSTEM SHALL validate a strict request schema before any paid external call.

1.2. THE request SHALL contain a UTF-8 `prompt` between 1 and 500 characters after trimming.

1.3. THE SYSTEM SHALL support only one-city, one-day requests using `WALK` or `DRIVE`.

1.4. WHEN the prompt is clearly off-topic, abusive without itinerary intent, or lacks place-and-time intent, THE SYSTEM SHALL return the canned `OFF_TOPIC` response without calling Claude, Places, or Routes.

1.5. WHEN the per-IP limit of five planning requests in the current UTC-hour bucket is exceeded, THE SYSTEM SHALL return `RATE_LIMITED` with the bucket-end retry time before other paid calls.

1.6. THE rate-limit key SHALL be a server-side HMAC of the client IP and SHALL expire; raw IP addresses SHALL NOT be stored in DynamoDB.

1.7. WHEN the normalized time window crosses local midnight, has an end at or before its start, or exceeds one calendar day, THE SYSTEM SHALL return `INVALID_TIME_WINDOW`.

1.8. WHEN the requested date is before the itinerary location's local current date, THE SYSTEM SHALL return `INVALID_DATE`.

## Requirement 2 — Typed intent and candidate selection

2.1. Claude SHALL return schema-validated structured data only. The raw model response SHALL never be rendered to the user.

2.2. The structured result SHALL include:

- city/locality query
- fixed origin query
- requested date or `null`
- local start and end times
- `WALK` or `DRIVE`
- return-to-origin boolean
- one to nine candidate stops in candidate order

2.3. Each candidate SHALL include `name`, bounded `category`, integer `priority` from 1 to 3, and visit-duration data with explicit provenance.

2.4. Explicit user duration instructions SHALL use provenance `user` only when the structured output supplies an exact prompt span containing the duration and the backend deterministically validates that span against the original request. An unsupported `user` claim SHALL make the model output invalid and trigger the bounded repair path; model-proposed durations SHALL use provenance `model_estimate`. Evidence spans are transient and SHALL NOT enter logs, shares, or the itinerary response.

2.5. User durations SHALL be integer minutes from 15 through 240. A value outside that range SHALL make the request invalid rather than being silently clamped.

2.6. Model estimates SHALL satisfy the category range below:

| Category | Minimum | Default | Maximum |
|---|---:|---:|---:|
| `quick_viewpoint` | 15 min | 20 min | 30 min |
| `landmark` | 30 min | 45 min | 75 min |
| `museum_gallery` | 60 min | 90 min | 180 min |
| `historic_religious_site` | 30 min | 60 min | 120 min |
| `neighborhood_market_park` | 30 min | 60 min | 120 min |
| `food_break` | 30 min | 60 min | 120 min |
| `experience_tour` | 60 min | 120 min | 240 min |
| `other` | 30 min | 60 min | 90 min |

2.7. WHEN model output violates its schema or a duration bound, THE SYSTEM SHALL make at most one structured repair attempt. A second failure SHALL return `MODEL_OUTPUT_INVALID`.

2.8. WHEN the requested date is omitted, THE SYSTEM SHALL defer the default until the origin timezone is grounded, then use that timezone's current local date.

## Requirement 3 — Places grounding and identity

3.1. THE SYSTEM SHALL ground the origin and each candidate with Places Text Search using the city/locality in the query and a bounded result count.

3.2. Production field masks SHALL request only required fields, including:

- `places.id`
- `places.displayName`
- `places.formattedAddress`
- `places.location`
- `places.primaryType`
- `places.timeZone`
- `places.currentOpeningHours`
- `places.regularOpeningHours`
- `places.photos`

3.3. `places.timeZone.id`, an IANA timezone identifier, SHALL be the schedule timezone source. `utcOffsetMinutes` SHALL NOT drive date arithmetic because it is only the current offset.

3.4. WHEN the origin cannot be resolved unambiguously, THE SYSTEM SHALL return `ORIGIN_NOT_FOUND` and stop.

3.5. WHEN a candidate cannot be resolved unambiguously within the requested locality, THE SYSTEM SHALL exclude it and return a `PLACE_NOT_FOUND` diagnostic.

3.6. WHEN multiple candidates resolve to the same Place ID, THE SYSTEM SHALL keep the earliest highest-priority candidate and return a `DUPLICATE_PLACE` diagnostic for each duplicate.

3.7. All retained stops SHALL use the same IANA timezone as the origin. A cross-timezone result SHALL be excluded with `OUTSIDE_LOCALITY` because the product supports one city and one local day.

3.8. WHEN a Places photo is retained, THE SYSTEM SHALL preserve every returned `authorAttributions` entry with the photo metadata.

## Requirement 4 — Opening-hours interpretation

4.1. THE SYSTEM SHALL interpret opening periods in the place's IANA timezone and requested local date.

4.2. THE SYSTEM SHALL record the local fetch date for `currentOpeningHours` and derive its documented seven-local-date coverage window in the place timezone. WHEN the requested date lies inside that window, THE SYSTEM SHALL use only current periods that intersect that date.

4.3. WHEN the requested date lies inside the current-hours coverage window and no usable period intersects it, THE SYSTEM SHALL treat the place as explicitly closed with `CLOSED_ON_DATE`; it SHALL NOT fall back to recurring hours.

4.4. OTHERWISE, WHEN the requested date is outside current-hours coverage and `regularOpeningHours` has usable periods for the requested local weekday, THE SYSTEM SHALL use those periods and mark the source `regular`.

4.5. WHEN neither source is usable, THE SYSTEM SHALL exclude the stop with `HOURS_UNAVAILABLE`. It SHALL NOT assume all-day availability.

4.6. THE parser SHALL support multiple opening intervals on one date, intervals crossing midnight, 24-hour places, truncated current periods, and intervals whose close date differs from the open date.

4.7. A visit SHALL fit entirely within one opening interval. Spanning a closed interval SHALL be infeasible.

4.8. WHEN arrival precedes a usable opening interval, THE schedule SHALL contain a first-class wait segment, and that wait SHALL count against the time window.

4.9. Ambiguous or nonexistent local times at daylight-saving transitions SHALL return `LOCAL_TIME_AMBIGUOUS` rather than being shifted silently.

## Requirement 5 — Place cache freshness

5.1. THE SYSTEM SHALL cache stable profile data, regular hours, and date-specific hours as separate DynamoDB items with separate application-enforced expirations.

5.2. Stable profile data SHALL have a 30-day freshness window.

5.3. Regular opening hours SHALL have a 7-day freshness window.

5.4. Date-specific hours SHALL expire no later than six hours after the end of the represented local date and SHALL never be reused for another date.

5.5. DynamoDB TTL deletion is asynchronous; therefore, THE application SHALL treat `expiresAt <= now` as a cache miss even if the item still exists.

5.6. A fresh profile cache hit SHALL NOT permit stale hours to be served.

## Requirement 6 — Directed travel matrix

6.1. THE SYSTEM SHALL call `computeRouteMatrix` with the fixed origin plus all grounded retained visit stops as both origins and destinations.

6.2. With nine visit stops, THE matrix SHALL contain at most 10 × 10 = 100 directed elements.

6.3. THE response field mask SHALL include `originIndex`, `destinationIndex`, `status`, `condition`, `distanceMeters`, and `duration`.

6.4. Every `[originIndex][destinationIndex]` element SHALL be stored independently. Reverse elements SHALL never be inferred or mirrored.

6.5. Missing, failed, or `ROUTE_NOT_FOUND` elements SHALL be represented as unreachable edges and SHALL NOT receive fabricated distance or duration.

6.6. WHEN no usable route exists from the origin to any candidate, THE SYSTEM SHALL return `NO_REACHABLE_STOPS`.

## Requirement 7 — Exact schedule solver

7.1. THE origin SHALL remain fixed. THE SYSTEM SHALL evaluate every permutation of the retained visit stops, up to 9! permutations.

7.2. For each order, THE SYSTEM SHALL simulate local time forward by applying directed travel, wait, visit, and optional return-to-origin travel.

7.3. An order SHALL be rejected when any required edge is unreachable, a visit cannot finish within one opening interval, or the completed route exceeds the user window.

7.4. Among feasible orders, THE SYSTEM SHALL minimize total directed travel seconds.

7.5. Ties SHALL be resolved by lower total waiting seconds, then earlier final completion, then lexicographic candidate-index order.

7.6. THE output SHALL expose arrival and departure times, travel legs, wait segments, opening constraints used, visit-duration provenance, total travel, and total waiting.

7.7. THE implementation SHALL be benchmarked at 8! and 9! in the Lambda-equivalent runtime before any latency claim is published.

7.8. Performance pruning MAY abandon a partial permutation only when it cannot beat the current best result; pruning SHALL NOT change exactness.

## Requirement 8 — Infeasibility and deterministic dropping

8.1. WHEN the full retained set has no feasible order, THE SYSTEM SHALL remove one least-essential stop and run the exact solver again.

8.2. Drop order SHALL be deterministic: lower importance first (`priority` 3 before 2 before 1), then narrower usable opening window, then longer visit duration, then later candidate index.

8.3. The process SHALL continue until a feasible schedule exists or no stops remain.

8.4. Every excluded or dropped stop SHALL remain visible in response diagnostics with a stable reason code and factual detail.

8.5. WHEN all stops are excluded or dropped, THE SYSTEM SHALL return `NO_FEASIBLE_ITINERARY` with diagnostics and SHALL NOT return an empty result as success.

8.6. The naive baseline SHALL use the exact final retained stop set in candidate order; it SHALL never include stops absent from the optimized result.

## Requirement 9 — Honest route comparison and real geometry

9.1. After solving, THE SYSTEM SHALL call `computeRoutes` once for the naive order and once for the optimized order.

9.2. Both calls SHALL use the same fixed origin, retained stop set, open-route versus return-to-origin rule, travel mode, departure-time policy, route modifiers, polyline quality, and encoding. Only stop order may differ. For an open route, each order's final retained stop is its destination; for a return route, the fixed origin is the destination and every retained stop is intermediate.

9.3. THE requests SHALL preserve the provided order and SHALL NOT ask Google to optimize waypoints.

9.4. THE field mask SHALL request route and leg distance, duration, and `routes.polyline.encodedPolyline`.

9.5. THE SYSTEM SHALL request a basic `HIGH_QUALITY` encoded polyline, not a traffic-colored or fabricated line.

9.6. Displayed comparison distance and travel duration SHALL come from the two `computeRoutes` responses. Solver feasibility SHALL still use the directed matrix and opening-hour simulation.

9.7. The naive order SHALL be simulated against the same opening constraints so the response can state whether and why it fails.

9.8. WHEN either geometry call fails or returns no route, THE SYSTEM SHALL mark the comparison `unavailable`, keep the valid schedule usable, and return a retryable diagnostic. It SHALL NOT draw straight lines or label matrix-only data as route geometry.

9.9. WHEN naive and optimized orders are identical, including every one-stop itinerary, THE SYSTEM SHALL return a `same_order` outcome with zero signed deltas and SHALL NOT claim savings. WHEN ordered route metrics disagree with the matrix objective, THE SYSTEM SHALL expose the signed real metrics and a typed `METRICS_DIVERGED` diagnostic; it SHALL NOT clamp a negative delta to zero.

## Requirement 10 — Google Maps handoff

10.1. THE SYSTEM SHALL build a documented `https://www.google.com/maps/dir/?api=1` URL using ordered place identifiers or coordinates and the selected travel mode.

10.2. THE full URL SHALL preserve the solved origin, stop order, destination, and return rule and SHALL be at most 2,048 characters to be marked valid.

10.3. Because mobile browsers support only three intermediate waypoints while other platforms support up to nine, THE response SHALL also contain deterministic browser-safe parts whenever the full route has more than three intermediate waypoints.

10.4. Each browser-safe part SHALL contain at most three intermediate waypoints, overlap the previous part at its boundary, preserve global order, and remain at most 2,048 characters.

10.5. THE SYSTEM SHALL never truncate, reorder, or silently remove a stop to satisfy a URL or platform limit.

10.6. WHEN a valid full URL cannot be built but all parts are valid, THE response SHALL expose the parts and an explicit full-route warning.

10.7. WHEN any required part is invalid, THE response SHALL return `HANDOFF_UNAVAILABLE` while preserving the Vialo schedule and map.

## Requirement 11 — Anonymous sharing

11.1. THE SYSTEM SHALL create a share record only after an explicit share request, not for every generated itinerary.

11.2. A share request SHALL carry the canonical shareable itinerary payload and a server-generated proof envelope containing an expiry and an HMAC over that expiry plus the canonical payload. THE server SHALL verify the unexpired proof in constant time before storage.

11.3. Shared records SHALL contain the computed itinerary and SHALL NOT contain the original prompt, client IP, raw model response, or API credentials.

11.4. Share identifiers SHALL be unguessable, URL-safe, and at least eight random characters.

11.5. Shared records SHALL expire after 30 days using both application expiry checks and DynamoDB TTL.

11.6. A missing, expired, or deleted share SHALL return `SHARE_NOT_FOUND` without revealing whether the identifier once existed.

11.7. Share creation SHALL return a separate creator deletion token exactly once. The stored record SHALL contain only a server-HMAC digest of that token. Deletion SHALL require the matching token; knowledge of the public share URL alone SHALL never authorize deletion.

11.8. Share creation SHALL be idempotent for a valid proof so retries do not create unbounded duplicate records.

## Requirement 12 — Reliability, security, and privacy

12.1. External wrappers SHALL enforce timeouts, bounded retry with jitter for retryable 429/5xx responses, and schema validation at every boundary.

12.2. The frontend SHALL receive approved typed fields and template-ready diagnostics only; raw provider errors and stack traces SHALL remain server-side.

12.3. Logs SHALL omit raw prompts, full IP addresses, API keys, photo URLs containing credentials, raw model bodies, and complete itinerary payloads.

12.4. Structured logs MAY include request ID, pipeline stage, latency, cache status, candidate/retained counts, provider status category, matrix size, permutations evaluated, and failure code.

12.5. Request IDs and provider correlation data SHALL NOT be presented as user identifiers.

12.6. API credentials SHALL be loaded only from server-side environment configuration. The Maps JavaScript browser key SHALL remain separately referrer-restricted.

12.7. Every response SHALL include a schema version so stored shares remain readable across compatible deployments.

## Stable diagnostic codes

`INVALID_INPUT`, `INVALID_DATE`, `INVALID_TIME_WINDOW`, `OFF_TOPIC`, `RATE_LIMITED`, `MODEL_OUTPUT_INVALID`, `ORIGIN_NOT_FOUND`, `PLACE_NOT_FOUND`, `DUPLICATE_PLACE`, `OUTSIDE_LOCALITY`, `HOURS_UNAVAILABLE`, `CLOSED_ON_DATE`, `LOCAL_TIME_AMBIGUOUS`, `ROUTE_NOT_FOUND`, `NO_REACHABLE_STOPS`, `NO_FEASIBLE_ITINERARY`, `COMPARISON_UNAVAILABLE`, `METRICS_DIVERGED`, `HANDOFF_UNAVAILABLE`, `SHARE_NOT_FOUND`, `PROVIDER_UNAVAILABLE`, `INTERNAL_ERROR`.

## Phase 2 acceptance gate

The requirements are approved for implementation only when reviewers confirm:

- day-does-not-fit behavior is deterministic and visible;
- missing hours never become assumed availability;
- place-not-found and off-topic requests have explicit outcomes;
- timezone arithmetic uses `places.timeZone.id`;
- visit-duration provenance and bounds are explicit;
- route comparison uses real ordered `computeRoutes` geometry;
- Maps handoff never silently changes the route;
- cache items cannot serve stale hours through a fresh profile entry.
