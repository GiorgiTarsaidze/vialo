---
inclusion: always
---

# Tech — Vialo

## Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React SPA (TypeScript) | Design-heavy, mobile-first. Deployed to S3 + CloudFront. |
| Backend | AWS Lambda (TypeScript, API Gateway) | Small typed API surface for planning and anonymous shares. No server to manage. |
| Storage | DynamoDB | Explicit anonymous shares, split-freshness place cache, and HMAC-keyed request limits. No relational needs. |
| AI | Claude (Anthropic) | Structured output for candidate stop selection. Never free text to the user. |
| Maps | Google Maps Platform (Places API New, Routes API, Maps JavaScript API) | Grounding, travel-time matrix, map preview, and the handoff. |
| Hosting | S3 + CloudFront + ACM cert on `vialo.place` | HTTPS enforced, global CDN. |
| DNS | Cloudflare (DNS-only, grey cloud) | Points at CloudFront distribution. |

## The 5-step pipeline

This is the core of Vialo. Each step uses the right tool for what it's actually good at.

### Step 1 — LLM selects candidate stops

Claude receives the user's natural-language request (city, time budget, interests, mode) and returns **typed structured output**: an array of candidate stops with name, approximate category, and suggested visit duration. The model is good at "what's worth seeing" — use it for that.

Do **not** use Places API for discovery. It's expensive, slow, and worse than the model at cultural/contextual recommendations.

### Step 2 — Places API grounds each stop

For each candidate, call Google Places `searchText` to resolve:
- `place_id` (the ground truth identifier)
- Coordinates (`location`)
- `currentOpeningHours` with date-specific periods when available
- `regularOpeningHours` as the recurring weekly fallback
- `timeZone.id`, the IANA timezone used for requested-date opening and schedule arithmetic
- `photos`, preserving every returned `authorAttributions` entry when a photo is displayed

The validated Places response contains no typical-visit-duration field. Visit duration is therefore a typed **estimate** proposed in Claude's structured candidate output, schema-validated and bounded to a documented category range. Explicit user durations retain separate `user` provenance. Keep provenance explicit in the response model and UI; never label a model estimate as Places-verified or measured data.

Use `timeZone.id` rather than `utcOffsetMinutes`. The former is an IANA timezone that supports requested-date daylight-saving arithmetic; the latter is only the place's current offset.

For opening hours, derive the documented seven-local-date coverage window from the `currentOpeningHours` fetch date in the place timezone. When the requested date is inside that window, use its intersecting current periods; no usable period means explicitly closed and must not fall back to recurring hours. Only dates outside that coverage may use `regularOpeningHours` for the local weekday. If neither source is usable, invoke the specified missing-hours behavior rather than inventing availability.

Results are **cached in DynamoDB** as separately expiring profile, regular-hours, and date-specific-hours items. Application code checks expiry before use because DynamoDB TTL cleanup is asynchronous; never serve stale hours merely because coordinates remain valid.

### Step 3 — Routes API computes the travel-time matrix

One call to `computeRouteMatrix` with the fixed origin plus all grounded visit stops as both origins and destinations. At the product cap of 9 visit stops, this is 10×10 = 100 directed elements in one call. Request `originIndex`, `destinationIndex`, `status`, `condition`, `distanceMeters`, and `duration`.

Treat the matrix as **directed**. The validated walking fixture returned 518 seconds in one direction and 508 seconds in the reverse direction for the same 592-meter pair. Store and evaluate every `[origin][destination]` element independently; never mirror one triangular half or assume symmetry.

### Step 4 — Exact ordering with time-window constraints

With ≤9 stops, there are at most 9! = 362,880 permutations (8! = 40,320 if origin is fixed). For each permutation:
1. Simulate the day forward: accumulate travel time, any required wait, and visit duration.
2. If arrival is before opening, wait until opening and expose that wait in the schedule.
3. Reject any permutation where a place is closed that day, the visit cannot finish before closing, or the completed route exceeds the user's time budget.
4. Among valid permutations, select the one with minimum total travel time; break ties by less waiting, earlier completion, then candidate-index order.

**Why brute-force and not a heuristic:**
- 9! permutations is ~360k iterations. Each is a bounded arithmetic and time-window check, so exhaustive search is tractable at this product limit. Benchmark the implementation in Lambda before making a latency claim.
- The result is **provably optimal** — not an approximation. This is a concrete differentiator over any heuristic or LLM-guessed ordering.
- The code is simple, testable, and has no edge cases from heuristic traps (local minima, constraint violations discovered late).
- There is no engineering benefit to a more complex algorithm at this scale. A heuristic would be premature optimization that makes the code harder to verify and the claims weaker.

**Infeasibility handling:** If no permutation satisfies all constraints, the solver progressively drops the least-essential stop (lowest user priority or most schedule-constrained) and re-solves. The response includes explicit diagnostics: which stops were dropped and why ("Arsenale closes at 17:00; with your 14:00 start, it can't fit after the other 5 stops").

### Step 5 — Build real comparison geometry and the Maps handoff

`computeRouteMatrix` does not return polylines. After solving, call `computeRoutes` twice with identical inputs except order: once for the retained candidate order and once for the optimized order. Request route/leg distance, duration, and `routes.polyline.encodedPolyline`; disable Google waypoint optimization. Displayed comparison metrics and both overlaid lines come from these paired real route responses. If either geometry call fails, omit both lines and report comparison unavailable rather than drawing straight segments.

Build a `https://www.google.com/maps/dir/?api=1` URL using documented Maps URL place-ID parameters and the selected `travelmode` (`walking` or `driving`). Preserve the solved order and origin/return requirement exactly. The full URL must be ≤2048 characters. Because mobile browsers support only three intermediate waypoints, also build deterministic overlapping browser-safe parts with at most three intermediates each when required. Never truncate, reorder, or silently remove stops; if neither a full URL nor valid parts can be built, keep the Vialo timeline and map usable and return an explicit handoff error.

## Infrastructure

### Frontend deployment
- S3 bucket with static website hosting disabled (CloudFront handles routing)
- CloudFront distribution with the ACM cert for `vialo.place`
- SPA routing: CloudFront custom error response returns `index.html` for 403/404

### Backend deployment
- Single Lambda function behind API Gateway (or Function URL)
- Environment variables for API keys and server-only HMAC secrets; no secrets in request payloads or logs
- Memory: 512MB (sufficient for brute-force permutation solver)
- Timeout: 30s (allows for Places API latency on uncached lookups)

### DynamoDB tables
- `place-cache`: `PLACE#<placeId>` partitions with `PROFILE`, `HOURS#REGULAR`, and `HOURS#DATE#<date>` sort keys; each item has application-checked expiry plus TTL
- `shared-itineraries`: `SHARE#<randomId>`, stores schema-validated computed itinerary only after an explicit share action plus an HMAC digest of the separate creator deletion token; TTL = 30 days
- `request-limits`: HMAC-derived IP bucket key, atomic count, and short TTL; never stores a raw IP

## Security rules — non-negotiable

1. **API keys server-side only.** The frontend bundle never contains Google or Anthropic credentials. The browser key for Maps JS API is referrer-restricted and has only the Maps JavaScript API enabled.
2. **Structured output only.** The model returns typed intent and candidate objects. No model prose is rendered to the page; deterministic code grounds, solves, and templates every result.
3. **Server-side scope check.** Before calling Claude or any paid API: is this a place-and-time request? Off-topic input gets a canned refusal with zero API spend.
4. **Per-IP rate limiting.** 5 requests/hour using a DynamoDB atomic counter keyed by a server-HMAC of the IP. Never persist or log the raw IP.
5. **Input length cap.** Max 500 characters for the user prompt. Reject longer input before processing.
6. **Never echo user input unescaped.** All text rendered in the frontend is sanitized. React's JSX escaping handles most cases; never use `dangerouslySetInnerHTML`.
7. **Budget alarms.** AWS Budget + GCP Budget alerts at 50%/90%/100%. A runaway loop must not cost real money.
8. **No credentials in the repository.** `.env` is gitignored from commit #1. Full git-history secret scan before submission.
9. **Data minimization.** Process prompts in memory; do not include raw prompts, full IPs, raw provider/model bodies, or secrets in logs or shared itineraries.
10. **Share capability separation.** Anonymous shares are public to anyone with the URL and expire after 30 days. The creator deletion token is returned separately, never embedded in the public URL, and only its server-HMAC digest is stored.