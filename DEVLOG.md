# Vialo Development Log

This log records meaningful implementation decisions, corrections, and validation results throughout the project.

## 2026-08-13 — Repository foundation and steering

### Completed

- Initialized a clean repository with secret and local-note exclusions committed before project artifacts.
- Defined persistent Kiro steering for the product, technical pipeline, repository structure, and design system.
- Frozen the product scope at four visible, testable features.
- Established the timeline and naive-versus-optimized route comparison as the signature product surfaces.

### Corrections made during steering

- Removed an unsupported assumption that a Places editorial summary supplies typical visit duration. The recorded API fixture must establish what data is actually available before the itinerary-engine spec defines duration handling.
- Replaced an unverified solver-latency claim with a requirement to benchmark the exhaustive implementation.
- Prohibited silently dropping waypoints when constructing the Google Maps handoff.
- Aligned solver and timeline behavior so an early arrival produces a visible wait rather than an invalid schedule.

### Google API validation gate passed

Real responses were captured under `docs/api-samples/` and validated before specification work:

- Places Text Search returned a stable place ID, address, coordinates, seven recurring opening periods, seven date-specific current periods, and 10 photos for Saint Mark's Basilica.
- Current opening periods contain explicit dates; regular periods provide the recurring weekly fallback.
- Photo records include author attribution. The UI must preserve linked attribution whenever it displays a photo.
- The Places response contains no typical-visit-duration field. Visit durations must remain explicit, bounded estimates rather than being described as Places-verified.
- Routes `computeRouteMatrix` returned four valid walking elements. The nonzero pair was 592 meters in both directions but 518 seconds outbound and 508 seconds inbound, proving the matrix must be handled as directed.
- Both fixture assertions passed, and a credential-pattern scan found no likely secrets.

### Remaining design input before the itinerary-engine specification

- Include place timezone data in production grounding so local opening periods and user-entered times are interpreted correctly.
- Define the bounded category ranges used to validate model-proposed visit-duration estimates.
- Define how real route polylines for the naive and optimized map comparison are obtained; a duration matrix alone does not contain geometry.

## 2026-08-15 — Agent-led visual workflow and AWS certificate

### Completed

- Configured the workspace to run the exact `@playwright/mcp@0.0.79` release for browser-based UI inspection.
- Added a project-local `ui-reviewer` Kiro agent and five progressive skills covering visual identity, mobile UX, route comparison, accessibility, and judge-first-impression review.
- Added lightweight hooks for repository safety plus frontend lint/typecheck validation once the frontend package exists.
- Replaced the cool teal direction with a light, warm system built from cream and white foundations, warm charcoal, deep plum, warm coral, and restrained butter, blush, and lilac fields.
- Verified core palette contrast pairs at 5.29:1–14.49:1.
- Verified the ACM certificate for `vialo.place` and `*.vialo.place` is issued after DNS validation.

### Kiro correction

The first reviewer startup exposed that a workspace MCP configuration was available to the default agent but was not inherited by the custom reviewer. The reviewer initially loaded only its built-in tools. Binding the same pinned Playwright server directly in the agent configuration fixed the gap; a second startup check exposed 23 browser tools, including viewport resize, accessibility snapshots, and screenshots.

### Design decision

The visual workflow will be agent-led rather than dependent on external design files. Visual impact must come from immediate hierarchy, the honest route-comparison reveal, the scheduled timeline, confident typography, and precise motion—not from extra controls, decorative effects, or dashboard complexity. Playwright evidence at mobile and desktop widths is required before a visual pass is claimed.

## 2026-08-15 — Itinerary-engine specification and experience blueprint

### Technical decisions locked

- Use Places `timeZone.id` as the authoritative IANA timezone for requested-date arithmetic. `utcOffsetMinutes` is current-only, so a separate Time Zone API call is unnecessary and the offset is never used to schedule another date.
- Treat `currentOpeningHours` as authoritative across its documented seven-local-date coverage. A covered date with no usable period is closed; recurring hours are only a fallback outside that coverage. Missing hours are never converted into assumed availability.
- Validate model-proposed visit durations against category bounds and preserve separate, verifiable provenance for explicit user durations.
- Include the fixed origin with up to nine visit stops in the directed matrix. The corrected maximum is 10 × 10 = 100 elements, not 9 × 9.
- Keep the exhaustive fixed-origin solver exact through deterministic tie-breaks and only safe pruning. Lambda latency remains a benchmark requirement rather than a claim.
- Generate comparison evidence with two ordered `computeRoutes` requests because `computeRouteMatrix` has no polyline. Both routes use the same retained stops and options; failed geometry never becomes a straight-line substitute.
- Build a full Maps URL plus deterministic overlapping browser-safe parts with no more than three intermediate waypoints each. No handoff path may truncate or reorder stops.
- Create anonymous shares only after an explicit action. Public share URLs remain separate from creator-only deletion tokens, and prompts, raw IPs, and raw provider/model bodies are excluded from stored shares and logs.

### Kiro specifications and design

- Added complete itinerary-engine requirements, technical design, and six-wave implementation tasks under `.kiro/specs/itinerary-engine/`.
- Added an agent-led three-screen frontend blueprint for the input hero, computed result, and shared permalink.
- Locked the comparison to one map with a coral dashed naive route and a heavier plum optimized route, real route metrics, explicit feasibility, signed deltas, and honest one-stop/same-order states.
- Defined responsive, keyboard, reduced-motion, attribution, loading, partial, infeasible, error, and expired-share acceptance behavior before implementation.

### Independent review and corrections

Independent backend, UX/accessibility, security/privacy, and release audits returned PASS with no blocker or major findings. Review follow-ups reconciled the mobile one-map order, made zero-distance matrix diagonal initialization explicit, reused strict protobuf-duration parsing for route geometry, and preserved fixed-window rate-limit behavior as an intentional low-cost guardrail.

## 2026-08-15 — Python Lambda architecture and model-provider boundary

### Architecture correction before implementation

The first backend specification inherited a TypeScript Lambda assumption from early steering. Before Phase 3 code began, the architecture was deliberately changed to one Python 3.12 Lambda behind API Gateway HTTP API. The corrected stack uses Lambda Powertools routing and telemetry, strict Pydantic v2 boundary models, direct Google REST adapters through `httpx`, boto3 repositories, standard-library `datetime`/`zoneinfo`, pytest with Hypothesis, Ruff, strict mypy, a committed `uv.lock`, and AWS SAM.

Public API JSON remains camelCase while Python remains idiomatic snake_case. Pydantic exports a versioned JSON Schema so the React TypeScript frontend can generate or verify contracts instead of relying on a shared backend language. The deterministic solver and opening-hours domain stay free of Lambda, AWS, Google, and model-provider imports.

### Model-provider decision

Candidate selection now depends on a narrow Python `CandidateSelector` protocol. Production wires one Anthropic Claude adapter with a separately configured server-side Anthropic API key and pinned model ID. This isolates the provider SDK without claiming runtime multi-provider selection or an untested fallback.

Official Kiro documentation was checked before considering Kiro credentials for the application. `KIRO_API_KEY` is documented for authenticating headless `kiro-cli chat --no-interactive` automation. Kiro usage documentation describes credits in terms of Kiro requests and agentic requests; it does not document direct model-provider API access or deployed-application inference paid from those credits. Vialo therefore does not place `KIRO_API_KEY` in Lambda and does not budget Kiro credits for production inference.

## 2026-08-15 — Phase 3 backend implementation and AWS deployment

### Implemented

- Added the Python 3.12 Lambda backend with strict camelCase Pydantic contracts, Lambda Powertools routing/telemetry, a provider-neutral `CandidateSelector`, and the production Anthropic adapter.
- Implemented the zero-spend scope guard, HMAC-keyed fixed-window rate limiting, deterministic user-duration evidence validation, and bounded category estimates.
- Implemented separate origin grounding, deterministic Places ambiguity handling, same-timezone enforcement, and split-freshness DynamoDB cache records for query resolution, profile, recurring hours, and requested-date current hours.
- Normalized explicit-date, recurring, split, overnight, always-open, and previous-day opening periods with requested-date clipping and explicit DST gap/fold rejection. Missing hours never imply open.
- Preserved the Routes matrix as directed and implemented exact fixed-origin permutation solving, deterministic tie-breaks, explicit waits, progressive dropping, and stable original matrix indices for naive simulation.
- Added two real ordered `computeRoutes` production calls for honest naive-versus-optimized geometry, documented Google Maps URL place-ID fields, browser-safe overlapping route parts, and a strict 2,048-character guard. Geometry failure omits both lines rather than inventing one.
- Added canonical HMAC share proofs, one-transaction proof claim/share creation, public 30-day shares, creator-only deletion tokens stored as server-HMAC digests, typed error routes, bounded retries, and sanitized provider failures.
- Built third-party packages into a dependency-only Python 3.12 ARM64 layer while retaining only first-party `vialo` source in the function artifact.

### Hardening and review

Two independent backend/infrastructure reviews passed without blocker or major findings. Follow-up hardening covered transport-wide `httpx.RequestError` retries, requested-date cache refresh despite a fresh profile, authoritative cached closures, malformed provider clock handling, atomic share creation, exact user-duration provenance, route-part reconstruction, and low-cardinality cache/latency telemetry. No prompt, raw IP, provider body, secret, or model prose is stored in shares or emitted to application/access logs.

### Local validation and exact-solver evidence

The final gate passed:

- 225 pytest tests with 85% statement coverage;
- Ruff lint and format checks;
- strict mypy across source and tests;
- source and transformed SAM validation plus a successful SAM build;
- source-only function/dependency-only layer separation;
- repository safety validation;
- ARM64 layer verification with two CPython 3.12 AArch64 native extensions, 33,643,491 uncompressed bytes, and 18,749,626 zipped bytes.

A final single benchmark run completed 8! in 0.215 seconds and 9! in 2.096 seconds. A separate warmed 10-sample Python 3.12 run measured nearest-rank p95:

| Case | Permutations | Warm-up | Median | p95 | Range |
|---|---:|---:|---:|---:|---:|
| 8! | 40,320 | 0.193 s | 0.189 s | 0.194 s | 0.187–0.194 s |
| 9! | 362,880 | 1.884 s | 1.899 s | 1.956 s | 1.847–1.956 s |

These are local host measurements, not a deployed 512 MB Lambda latency claim.

### AWS deployment and smoke evidence

CloudFormation created the isolated `vialo-backend-dev` stack in `us-east-1`. The API endpoint is `https://ap9i8up7k7.execute-api.us-east-1.amazonaws.com`. The deployed resources are one Python 3.12 ARM64 Lambda, one dependency layer version, one HTTP API and default stage, two seven-day log groups, one explicit IAM role, and three on-demand DynamoDB tables. The artifact bucket is private, AES-256 encrypted, bucket-owner enforced, TLS-only, and expires objects after seven days.

Deployed checks verified 512 MB memory, a 30-second timeout, no reserved or provisioned concurrency, PAY_PER_REQUEST billing, PITR disabled, TTL enabled, the exact four API routes, scoped IAM resources/actions without wildcards, and the required `Project=vialo`, `vialo=true`, `Environment=dev`, and `ManagedBy=sam` tags on every taggable resource. Lambda layer-version resources are not taggable through either CloudFormation or the Lambda tagging API; both attempted API forms were rejected, so the layer is the documented non-taggable exception.

Only zero-provider-spend smokes were run because deployed provider values remain placeholders:

- empty prompt → `400 INVALID_INPUT`;
- off-topic prompt → `400 OFF_TOPIC`;
- missing share → `404 SHARE_NOT_FOUND`;
- delete without creator token → `401 INVALID_INPUT`.

The successful off-topic invocation loaded the complete ARM64 function and layer, resolving the earlier local host inability to execute ARM64 containers. CloudWatch emitted structured request/cold-start/share metrics. Lambda logs contained no raw prompt or credential material, and API access logs contained only request ID, route key, status, response length, and integration latency.

### Remaining live-evidence gates

Real provider-dependent itinerary generation and paired route geometry were not invoked because Anthropic, Google Places, and Google Routes credentials were unavailable. A sanitized live `computeRoutes` geometry fixture and a deployed 512 MB solver benchmark therefore remain open evidence tasks; production has no fixture, simulated, or hard-coded fallback. Before enabling the complete flow, configure the three server-side provider credentials plus a supported pinned Anthropic model ID, create a separate referrer-restricted Maps JavaScript API browser key, and configure AWS/GCP budget notifications at 50%, 90%, and 100%.

## 2026-08-15 — Bedrock migration, hard spend cap, and live provider validation

### Provider and cost-control migration

- Replaced the direct Anthropic SDK/runtime key with a provider-isolated `BedrockCandidateSelector` using boto3 Converse and the active `us.anthropic.claude-sonnet-4-6` inference profile. The `CandidateSelector` protocol remains unchanged so another adapter can be added without coupling provider code to the pipeline.
- Scoped Lambda IAM to the inference-profile ARN and its three exact Sonnet 4.6 backing model ARNs. Botocore opaque retries are disabled so each application reservation maps to one wire call.
- Added a fail-closed DynamoDB monthly spend circuit breaker. Every initial or repair Converse invocation atomically reserves conservative input plus maximum-output cost before the call, then refunds only confirmed unused usage. Missing/malformed usage, provider ambiguity, or settlement failure retains the reservation.
- Set the application cap to 5,000,000 micro-USD ($5) with deliberately conservative $4/M input and $20/M output rates. This synchronous guard is separate from delayed AWS Budget billing alerts.
- Retained the HMAC-keyed five accepted planning requests per IP per UTC hour and added API Gateway default throttling at 2 requests/second with burst 5.

### Google and live-integration corrections

- Configured only the server-restricted Google key in Lambda; the separate browser key remains frontend-only.
- A live walking `computeRoutes` request established that Google rejects `routingPreference` for `WALK` and `BICYCLE`. Vialo now omits it for walking and sends `TRAFFIC_UNAWARE` only for driving, with request-body regression tests for matrix and geometry calls.
- Captured `docs/api-samples/routes-venice-geometry.json`, a sanitized live walking response containing two legs, 1,526 meters, 1,286 seconds, and a real encoded polyline. Integration tests consume this canonical fixture; production never uses it as fallback data.
- Live Sonnet output exposed an ambiguous prompt contract: the model emitted `index` instead of `candidate_index`. The initial and repair instructions now require the exact key, with regression coverage.
- Live origin grounding exposed that a correct locality qualifier such as `Hotel Danieli, Venice` weakened canonical-name scoring. Grounding now removes known locality tokens only for place-name similarity while retaining locality address matching and ambiguity rejection.

### Deployment and live evidence

CloudFormation updated `vialo-backend-dev` to `UPDATE_COMPLETE`. The deployed stack uses Python 3.12 ARM64, 512 MB memory, a 30-second timeout, the pinned Sonnet 4.6 profile, exact Bedrock IAM resources, the server Google key, the $5 cap, API throttling, and a TLS 1.2 REGIONAL `api.vialo.place` domain with a `$default` mapping.

The active execute-api endpoint is `https://ap9i8up7k7.execute-api.us-east-1.amazonaws.com`. AWS reports the custom-domain DNS target as `d-qlg5m9tufa.execute-api.us-east-1.amazonaws.com`; the Cloudflare DNS-only CNAME remains a manual action, so `api.vialo.place` is not yet claimed live.

Bedrock first-time-use registration propagated successfully and a minimal Converse access check returned usage metadata. Public planning requests exercised typed model errors, grounding, infeasibility handling, and the per-IP guard; the sixth attempt from the same public source received `429 RATE_LIMITED` after five accepted requests.

A controlled production Lambda integration using a reserved TEST-NET source IP returned HTTP 200 and schema version 1 with:

- two grounded retained stops and real opening intervals;
- two visit entries and two directed travel entries;
- an available naive-versus-optimized comparison with two real 421-character encoded polylines;
- two Google Maps handoff URLs;
- no raw prompt field.

That successful invocation settled one Bedrock call with 432 input tokens, 860 output tokens, and 18,929 conservative micro-USD. The monthly `reservedMicroUsd` total was 191,090, safely below the 5,000,000 cap. Earlier provider ambiguity remains conservatively accounted rather than deleted.

### Final validation

The post-migration release gate passed with 279 tests and 86% statement coverage, Ruff lint/format checks, strict mypy, source and transformed SAM validation, a successful SAM build, ARM64 layer verification, and repository safety validation. The dependency layer contains one CPython 3.12 AArch64 native extension, 31,638,313 uncompressed bytes, and 18,099,160 zipped bytes.

One release run exposed a flaky Moto-only concurrency result because Moto's in-memory backend can lose concurrent writes even though DynamoDB conditionally updates a single item atomically. The test now preserves genuinely concurrent callers while serializing only the emulated storage operation to model DynamoDB per-item linearizability and still evaluates the production condition. It passed 20 consecutive stress runs plus the full suite; persisted and caller-acknowledged reservations remained under the cap.

## 2026-08-16 — Custom API hostname and Tbilisi production smoke

Cloudflare now publishes the DNS-only `api.vialo.place` CNAME to the exact REGIONAL API Gateway target. Live verification confirmed DNS resolution, the ACM `vialo.place`/`*.vialo.place` certificate, hostname matching, TLS 1.3 negotiation under the AWS TLS 1.2 minimum policy, one `$default` API mapping, and an expected typed share `404` through the custom hostname.

A bounded public Tbilisi request also exercised the complete production path. The literal origin `Liberty Square` was correctly rejected as ambiguous because Places returned two equally ranked results; Google's canonical `Freedom Square` query resolved uniquely. Retrying with that canonical origin returned HTTP 200, schema version 1, and an explicitly partial walking round trip for 13:00–17:00 in `Asia/Tbilisi`:

- Metekhi Church and Anchiskhati Basilica were retained with current opening intervals and 30-minute bounded model-estimate visits.
- Three real walking legs totaled 3,136 meters and 2,705 seconds, returning to Freedom Square at 14:45:05.
- The naive and optimized orders were identical, with paired real 477-character polylines; no optimization saving was claimed.
- Narikala Fortress was excluded because usable opening hours were unavailable, and Old Town Abanotubani was excluded because Places could not resolve the generated district label unambiguously. Both reasons remained visible rather than being silently ignored.
- The response included a full Google Maps round-trip URL and one browser-safe part, with no raw prompt field.

The successful call settled 453 Bedrock input tokens, 449 output tokens, and 10,793 conservative micro-USD. Monthly tracked reservation remained 212,896 of the 5,000,000 micro-USD cap. API access logs contained only the configured request ID, route, status, response length, and integration latency; an exact prompt and configured-secret scan of recent logs passed.

## 2026-08-16 — Phase 3 frontend and secure CloudFront deployment

### React experience and contract safety

- Built the mobile-first React 18 + TypeScript + Vite SPA from the locked frontend blueprint: input hero, factual pipeline loading, typed errors, result statement, honest naive-versus-optimized comparison, one Maps JavaScript overlay, complete travel/wait/visit timeline, dropped-stop diagnostics, Maps handoff, privacy/terms routes, explicit anonymous sharing, read-only permalinks, and creator-only deletion.
- Preserved place-local wall times from the API instead of converting through the viewer timezone. Timeline entries use the backend's one-based matrix stop index, while comparison route order continues to use candidate indices.
- Added a generated Pydantic JSON Schema artifact and exact backend drift test. Frontend runtime guards reject malformed responses; production has no fixture or hard-coded itinerary fallback.
- Pinned the frontend dependency graph, self-hosted Inter and Newsreader, disabled public source maps, and reduced `npm audit` to zero known vulnerabilities.

### Hosting and deployment

CloudFormation updated `vialo-backend-dev` to `UPDATE_COMPLETE` and added:

- private AES-256 encrypted S3 bucket `vialo-frontend-381492291672-us-east-1-dev` with all public-access blocks, bucket-owner enforcement, retention policies, and no website endpoint;
- CloudFront distribution `E1M7B5Z8A2A3Z8` at `d1topuming9zvf.cloudfront.net`, using Origin Access Control and a bucket policy scoped to that distribution;
- ACM-backed `vialo.place` alias, HTTPS redirects, HTTP/2+3, CSP/HSTS/nosniff/frame/referrer headers, extensionless SPA rewriting, and uncached same-origin `/api/*` proxying that does not mask API or asset failures.

The deployment script supplies the browser Maps key only at build time, gives hashed assets immutable caching, keeps `index.html` uncached, and invalidates the two entry points. Live smokes confirmed SPA routes, typed API 404 preservation, private-origin asset failure preservation, security headers on frontend and API responses, direct S3 403, and continued `api.vialo.place` operation.

### Live browser and sharing evidence

Playwright reviewed the deployed application at 360, 390, and 1440 pixels. There was no horizontal overflow. Keyboard-visible skip navigation, 44-pixel targets, complete semantic timeline labels, and emulated reduced motion all passed. One exact-date Tbilisi request returned a real computed partial itinerary with two retained grounded stops, travel and wait rows, a dropped-stop reason, paired route metrics/geometry, and a Maps handoff.

Live share creation initially returned 400 because the strict Pydantic boundary validated decoded JSON in Python mode, rejecting canonical ISO date/datetime and enum strings. The share API now uses `CreateShareRequest.model_validate_json`; a regression round-trips a JSON-serialized itinerary through the route. After redeployment, share create/read/delete returned 201/200/204, the creator capability remained only in local storage, deletion transitioned to the generic unavailable screen, and a fresh GET returned 404.

The final release gate passes 291 backend tests and 54 frontend tests, Ruff, ESLint, strict mypy and TypeScript, source and transformed SAM validation, ARM64 layer verification, production frontend build, repository safety checks, and zero npm vulnerabilities. An independent final UI/infrastructure audit returned PASS with no blockers.

### Remaining production-host action

The Cloudflare root record is not yet configured. Add a DNS-only root CNAME/flattened record from `vialo.place` to `d1topuming9zvf.cloudfront.net`. The browser key is intentionally restricted to `https://vialo.place/*`, so the temporary CloudFront hostname receives Google's expected `RefererNotAllowedMapError`; after DNS propagation, re-verify root TLS, same-origin API routing, and the visible Maps overlay before claiming the root hostname live.
