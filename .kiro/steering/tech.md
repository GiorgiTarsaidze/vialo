---
inclusion: always
---

# Tech — Vialo

## Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | React SPA (TypeScript) | Design-heavy, mobile-first. Deployed to S3 + CloudFront. |
| Backend | AWS Lambda (TypeScript, Function URL or API Gateway) | One endpoint: prompt in, scheduled itinerary out. No server to manage. |
| Storage | DynamoDB | Anonymous share permalinks + place-lookup cache. No relational needs. |
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
- `regularOpeningHours` (periods for the requested day)
- `photos` (first reference for display)
- The verified place identity used alongside a typed visit duration

Visit duration is required scheduling input, but the validated Places fields do not yet establish which response field supplies it. The itinerary-engine spec must resolve this from the recorded Phase 1 fixture. Do not assume `editorialSummary` contains a duration, and never present an estimated duration as Places-verified data.

Results are **cached in DynamoDB** keyed by normalized place identity and locality. Define separate freshness rules for stable place data and opening hours in the itinerary-engine spec; do not serve stale opening hours merely because coordinates remain valid.

### Step 3 — Routes API computes the travel-time matrix

One call to `computeRouteMatrix` with all grounded stops as both origins and destinations. For 9 stops: 9×9 = 81 elements, one API call. Returns real walking (or driving) durations in seconds.

### Step 4 — Exact ordering with time-window constraints

With ≤9 stops, there are at most 9! = 362,880 permutations (8! = 40,320 if origin is fixed). For each permutation:
1. Simulate the day forward: accumulate travel time, any required wait, and visit duration.
2. If arrival is before opening, wait until opening and expose that wait in the schedule.
3. Reject any permutation where a place is closed that day, the visit cannot finish before closing, or the completed route exceeds the user's time budget.
4. Among valid permutations, select the one with minimum total travel time.

**Why brute-force and not a heuristic:**
- 9! permutations is ~360k iterations. Each is a bounded arithmetic and time-window check, so exhaustive search is tractable at this product limit. Benchmark the implementation in Lambda before making a latency claim.
- The result is **provably optimal** — not an approximation. This is a concrete differentiator over any heuristic or LLM-guessed ordering.
- The code is simple, testable, and has no edge cases from heuristic traps (local minima, constraint violations discovered late).
- There is no engineering benefit to a more complex algorithm at this scale. A heuristic would be premature optimization that makes the code harder to verify and the claims weaker.

**Infeasibility handling:** If no permutation satisfies all constraints, the solver progressively drops the least-essential stop (lowest user priority or most schedule-constrained) and re-solves. The response includes explicit diagnostics: which stops were dropped and why ("Arsenale closes at 17:00; with your 14:00 start, it can't fit after the other 5 stops").

### Step 5 — Build the Google Maps URL

Build a `https://www.google.com/maps/dir/?api=1` URL using the documented Maps URL place-ID parameters for the ordered stops and the selected `travelmode` (`walking` or `driving`). Preserve the solved order and the user's origin/return requirement exactly.

Guard: the final URL must be ≤2048 characters and respect the 9-stop product cap. Never truncate or silently remove stops to make the handoff fit. If the guard fails, keep the Vialo timeline and map usable and return an explicit handoff error; any leg-splitting fallback must be specified and tested before it is claimed as functional.

## Infrastructure

### Frontend deployment
- S3 bucket with static website hosting disabled (CloudFront handles routing)
- CloudFront distribution with the ACM cert for `vialo.place`
- SPA routing: CloudFront custom error response returns `index.html` for 403/404

### Backend deployment
- Single Lambda function behind API Gateway (or Function URL)
- Environment variables for all API keys (GOOGLE_PLACES_KEY, GOOGLE_ROUTES_KEY, ANTHROPIC_API_KEY)
- Memory: 512MB (sufficient for brute-force permutation solver)
- Timeout: 30s (allows for Places API latency on uncached lookups)

### DynamoDB tables
- `place-cache`: partition key = `normalizedName#city`, sort key = `lookupDate`
- `shared-itineraries`: partition key = `shareId` (nanoid, 8 chars), stores full itinerary JSON, TTL = 30 days

## Security rules — non-negotiable

1. **API keys server-side only.** The frontend bundle never contains Google or Anthropic credentials. The browser key for Maps JS API is referrer-restricted and has only the Maps JavaScript API enabled.
2. **Structured output only.** The model returns a typed itinerary object. No free text is ever rendered from the model to the page. This kills most prompt injection vectors.
3. **Server-side scope check.** Before calling Claude or any paid API: is this a place-and-time request? Off-topic input gets a canned refusal with zero API spend.
4. **Per-IP rate limiting.** 5 requests/hour — generous for judges, hostile to scrapers. Implemented at API Gateway or Lambda level.
5. **Input length cap.** Max 500 characters for the user prompt. Reject longer input before processing.
6. **Never echo user input unescaped.** All text rendered in the frontend is sanitized. React's JSX escaping handles most cases; never use `dangerouslySetInnerHTML`.
7. **Budget alarms.** AWS Budget + GCP Budget alerts at 50%/90%/100%. A runaway loop must not cost real money.
8. **No credentials in the repository.** `.env` is gitignored from commit #1. Full git-history secret scan before submission.
