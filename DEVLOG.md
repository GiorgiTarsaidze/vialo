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

The visual workflow will be agent-led rather than dependent on Figma. Visual impact must come from immediate hierarchy, the honest route-comparison reveal, the scheduled timeline, confident typography, and precise motion—not from extra controls, decorative effects, or dashboard complexity. Playwright evidence at mobile and desktop widths is required before a visual pass is claimed.
