# Itinerary Engine Implementation Tasks

**Status:** Not started
**Scope:** Backend only
**Inputs:** [`requirements.md`](requirements.md), [`design.md`](design.md)

## Execution rules

- Execute tasks in wave order; tasks marked parallel may run concurrently.
- Use exact dependency versions and commit the lockfile when packages are introduced.
- Keep external providers behind interfaces and test through recorded fixtures or synthetic pure-domain data.
- Do not expose fixture data as production behavior.
- Complete and validate each task before marking its checkbox.
- Record material corrections and benchmark results in `DEVLOG.md`.

## Wave 1 — Workspace, schemas, and pure time logic

- [ ] **1. Create the backend TypeScript package and validation foundation**
  - Add pinned runtime/test dependencies, strict TypeScript, Vitest, and production/test scripts.
  - Create directories from structure steering and direct imports without barrel files.
  - Add environment schema with placeholders documented in `.env.example`.
  - _Requirements: 1.1–1.3, 12.6_

- [ ] **2. Implement request, intent, provider, and response schemas** *(parallel after task 1)*
  - Define strict Zod schemas and inferred TypeScript types.
  - Encode category-specific duration bounds and provenance.
  - Define stable diagnostic codes and schema version 1.
  - Test unknown keys, invalid ranges, stop cap, and malformed provider values.
  - _Requirements: 1, 2, 3, 12.1, 12.7_

- [ ] **3. Implement timezone and opening-hours normalization** *(parallel after task 1)*
  - Use the IANA `timeZone.id` and a pinned Temporal-compatible implementation.
  - Resolve local today after origin grounding.
  - Derive the seven-local-date current-hours coverage window; normalize current, regular, split, overnight, truncated, 24-hour, and closed periods without recurring-hours fallback inside authoritative coverage.
  - Reject ambiguous/nonexistent local times and missing hours.
  - Add exhaustive unit tests around DST and period boundaries.
  - _Requirements: 2.8, 3.3, 4_

**Wave 1 demo:** Pure functions turn typed place periods into requested-date open intervals and reject every unsupported time case explicitly.

## Wave 2 — Guardrails and Claude candidate selection

- [ ] **4. Implement input validation and zero-spend scope guard**
  - Validate prompt length and basic itinerary intent before provider calls.
  - Return approved `INVALID_INPUT` and `OFF_TOPIC` templates.
  - Test valid terse prompts, obvious off-topic input, abusive input, and boundary lengths.
  - _Requirements: 1.1–1.4_

- [ ] **5. Implement the DynamoDB rate limiter** *(parallel with task 4)*
  - HMAC client IP with a server-only salt.
  - Use atomic UTC-hour-bucket updates and expiry.
  - Return retry time after five accepted requests.
  - Test concurrency, rollover, expiry, and absence of raw IP storage/logging.
  - _Requirements: 1.5–1.6, 12.3–12.4_

- [ ] **6. Implement Claude structured intent and candidate selection**
  - Build the schema-constrained request and approved system prompt.
  - Preserve candidate order, priorities, category, duration, and provenance.
  - Verify every `user` duration through an exact prompt span and deterministic duration parser, then strip the evidence.
  - Add one bounded repair attempt for invalid structured output.
  - Mock the HTTP boundary and test invalid schema, excess stops, valid user overrides, and fabricated/mismatched duration evidence.
  - _Requirements: 2_

**Wave 2 demo:** A prompt produces validated typed intent and bounded candidates; invalid/off-topic/rate-limited requests stop before paid map calls.

## Wave 3 — Places grounding and split-freshness cache

- [ ] **7. Implement the Places Text Search adapter**
  - Request the exact production field mask, including `places.timeZone` and attribution-bearing photos.
  - Resolve origin/candidates within locality and reject ambiguity.
  - Deduplicate by Place ID and enforce one timezone.
  - Test against the canonical Places fixture plus a typed timezone augmentation.
  - _Requirements: 3_

- [ ] **8. Implement the `place-cache` repository** *(parallel with task 7)*
  - Add `PROFILE`, `HOURS#REGULAR`, `HOURS#DATE`, and query-resolution item handling.
  - Enforce application expiry separately from DynamoDB TTL.
  - Test fresh, stale, partially fresh, corrupt, and write-failure cases.
  - _Requirements: 5_

- [ ] **9. Compose grounding, cache, and hours selection**
  - Prefer fresh cache components independently.
  - Populate separately expiring items from live responses.
  - Produce typed dropped diagnostics for not found, duplicate, locality, timezone, hours, and closure.
  - _Requirements: 3–5, 8.4_

**Wave 3 demo:** Candidate names become verified Place IDs with IANA timezone, correct requested-date intervals, photo attribution, and independently fresh cache records.

## Wave 4 — Directed matrix and exact solver

- [ ] **10. Implement the Routes matrix adapter**
  - Build origin + retained stop inputs with a maximum of ten points.
  - Request and parse the six required matrix fields.
  - Initialize missing cells as unreachable and preserve directed asymmetry.
  - Assert the canonical fixture remains 592m with 518s/508s reverse durations.
  - _Requirements: 6_

- [ ] **11. Implement exact permutation scheduling** *(parallel pure-domain work after task 2)*
  - Simulate travel, wait, visits, split intervals, window end, and optional return.
  - Apply the objective and deterministic tie-break cascade.
  - Add property/invariant tests and focused synthetic scenarios.
  - _Requirements: 7_

- [ ] **12. Implement deterministic stop dropping and diagnostics**
  - Apply priority/window/duration/index removal order.
  - Re-solve exactly after each removal.
  - Build factual template parameters without LLM prose.
  - Build naive retained order and simulate its feasibility.
  - _Requirements: 8, 9.7_

- [ ] **13. Benchmark exactness at the product cap**
  - Benchmark representative 8! and 9! schedules after warm-up in a Lambda-equivalent runtime.
  - Record median/p95 and permutations evaluated in `DEVLOG.md`.
  - Add safe branch-and-bound pruning only if required; prove outputs match exhaustive reference cases.
  - _Requirements: 7.7–7.8_

**Wave 4 demo:** Synthetic and fixture-backed inputs produce a deterministic provably optimal schedule with visible waits and explicit dropped-stop reasons.

## Wave 5 — Real geometry and handoff

- [ ] **14. Implement the ordered `computeRoutes` adapter**
  - Preserve caller order with optimization disabled.
  - Build origin/intermediate/destination fields mechanically for open and return routes, including the zero-intermediate one-stop case.
  - Request high-quality encoded route and leg geometry/metrics with the same departure-time policy and modifiers.
  - Capture and sanitize a real geometry response fixture before claiming integration completion.
  - Test request parity between naive and optimized calls.
  - _Requirements: 9.1–9.5_

- [ ] **15. Build the honest comparison response**
  - Call geometry for the same retained stops in naive and optimized order.
  - Use signed route-response deltas and never hide unfavorable metrics.
  - Return explicit one-stop/same-order outcomes and `METRICS_DIVERGED` when route totals contradict the matrix objective.
  - Attach naive feasibility diagnostics and shared comparison bounds inputs.
  - Omit both route lines and mark unavailable if either call fails.
  - _Requirements: 8.6, 9.6–9.8_

- [ ] **16. Implement full and browser-safe Maps URLs** *(parallel with task 15)*
  - Build aligned text/coordinate and Place ID parameters.
  - Enforce the 2,048-character guard.
  - Partition routes into overlapping parts with no more than three intermediates each.
  - Test 1–9 stops, return routes, special characters, full URL failure, and part failure.
  - _Requirements: 10_

**Wave 5 demo:** The response contains two real route polylines and metrics plus a full Google Maps handoff and honest browser-safe parts without route mutation.

## Wave 6 — Sharing, orchestration, and reliability

- [ ] **17. Implement explicit anonymous sharing**
  - Generate and constant-time verify the expiring canonical itinerary HMAC proof envelope.
  - Make proof retries idempotent and store only validated computed output after `POST /shares`.
  - Return a creator deletion token once, store only its server-HMAC digest, and require it for `DELETE /shares/{id}`.
  - Enforce random ID, 30-day application expiry, and DynamoDB TTL.
  - Test prompt/IP/duration-evidence/provider-body omission, replay, unauthorized deletion, and expired/not-found behavior.
  - _Requirements: 11, 12.3_

- [ ] **18. Implement provider resilience and structured observability** *(parallel with task 17)*
  - Add per-call timeout and at most two jittered retries for retryable failures.
  - Add request/pipeline latency, cache, matrix, solver, and stable-code logs.
  - Add tests proving prompts, IPs, secrets, and raw provider/model bodies never enter logs.
  - _Requirements: 12.1–12.5_

- [ ] **19. Compose the Lambda/API handler**
  - Wire validation → guard → rate limit → Claude → Places/cache → matrix → solver → geometry → handoff.
  - Implement `POST /itineraries`, `POST /shares`, `GET /shares/{id}`, and creator-authorized `DELETE /shares/{id}`.
  - Map all failures to typed status codes without raw internals.
  - _Requirements: all_

- [ ] **20. Add integration and contract tests**
  - Mock all provider HTTP boundaries using canonical and newly captured sanitized fixtures.
  - Test complete, partial, no-feasible, provider-error, one-stop/same-order, signed metric divergence, comparison-unavailable, handoff-fallback, share create/read/delete, and rate-limit flows.
  - Snapshot only stable typed contracts, never provider prose.
  - _Requirements: all_

- [ ] **21. Run the backend completion gate**
  - Run unit/integration tests, typecheck, lint, build, diff checks, and credential scan.
  - Confirm exact 9-stop benchmark evidence is recorded.
  - Confirm no feature uses hard-coded production results.
  - Append the implementation outcome and corrections to `DEVLOG.md`.

**Wave 6 demo:** Prompt in → grounded, feasible, comparison-ready typed response out; explicit sharing works without storing prompts.

## Deferred to frontend tasks

The backend exposes typed fields for the following but does not implement their UI:

- timeline and wait rendering;
- naive/optimized map overlay and reveal;
- place-photo credits;
- estimated/planned duration labels;
- full-route versus browser-safe handoff presentation;
- dropped-stop diagnostics;
- shared permalink screen.

## Backend completion definition

The itinerary engine is complete only when all tasks are checked, tests and benchmark pass, a real sanitized geometry fixture exists, public claims match evidence, and all provider credentials remain outside Git history.
