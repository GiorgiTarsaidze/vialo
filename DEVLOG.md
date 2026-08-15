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
