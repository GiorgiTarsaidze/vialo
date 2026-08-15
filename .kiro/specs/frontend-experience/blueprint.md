# Vialo Frontend Experience Blueprint

**Status:** Design locked for Phase 3 implementation
**Method:** Agent-led, browser-validated, no external design-file dependency

## 1. Experience contract

A first-time visitor must understand within five seconds that Vialo turns one city-day request into a schedule that fits. A judge must understand the optimization benefit within four seconds of the result appearing.

The experience has three screens:

1. Input hero
2. Computed result
3. Shared permalink

The interface is not conversational. There is no message history, avatar, chat bubble, assistant voice, or model prose.

## 2. Visual composition

- Use warm cream and white for roughly 80% of each viewport.
- Use warm charcoal and deep plum for structure and action.
- Use butter, blush, or lilac as restrained fields; no more than two pastel families in one viewport.
- Use warm coral only for the naive route and related status.
- Use Newsreader for the hero and concise outcome statements; use Inter everywhere operational.
- Create impact through scale, spacing, aligned times, route geometry, and one explanatory reveal—not decoration.
- No gradients, glass effects, cool corporate blue, oversized card grids, or decorative map pins.

## 3. Shared shell

All screens use:

- 16px mobile gutters, 24–32px larger gutters, 1200px maximum content width;
- compact wordmark linking home;
- main landmark with one visible page heading;
- minimal footer with Privacy, Terms, GitHub, and required attribution links;
- 44 × 44px minimum interactive targets;
- visible focus rings and reduced-motion support.

## 4. Screen 1 — Input hero

### Purpose

Communicate outcome, accept one natural-language request, and provide three examples without exposing implementation details.

### Mobile wireframe — 360px

```text
┌──────────────────────────────────┐
│ vialo.                           │
│                                  │
│ Describe your day.               │
│ Get one that actually fits.      │
│                                  │
│ Verified stops, real hours,      │
│ and the shortest feasible order. │
│                                  │
│ ┌──────────────────────────────┐ │
│ │ Venice, 09:00–17:00,        │ │
│ │ architecture and quiet      │ │
│ │ streets, on foot            │ │
│ └──────────────────────────────┘ │
│                         0 / 500  │
│                                  │
│ ┌──────────────────────────────┐ │
│ │ Build my day                 │ │
│ └──────────────────────────────┘ │
│                                  │
│ Try an example                   │
│ [ Venice morning ]               │
│ [ Napoli essentials ]            │
│ [ Lisbon viewpoints ]            │
│                                  │
│ Privacy · Terms · GitHub          │
└──────────────────────────────────┘
```

### Desktop

Use one centered 640px composition rather than a split marketing layout. The headline may use two lines at `display-xl`. The input remains the dominant object. Example buttons sit in one wrapping row. Do not add testimonials, feature grids, or pipeline diagrams above the fold.

### Interaction

- Example selection fills but does not submit the input.
- Submit is disabled for empty or over-limit input.
- Enter with the platform modifier submits; plain Enter creates a newline.
- Inline errors explain the next correction and preserve input.
- A short note below the input says not to enter sensitive personal information and links to Privacy.

## 5. Loading transition

Keep the user on the input composition while the result shell replaces it without a full-page jump.

```text
Building a day that fits
· Finding places
· Checking opening hours
· Measuring travel
· Solving the order
· Drawing the routes
```

The synchronous planning endpoint does not expose live stage progress, so these are a static factual summary of work—not changing checkmarks or a claimed current stage. If real progress telemetry is added later, states may advance only from that telemetry. There are no percentages or invented completion estimates. Skeleton blocks match the final comparison and timeline widths. After eight measured seconds, show “This is taking longer than usual” without changing the stage facts.

Reduced motion uses static state changes. Standard motion uses a single 240–360ms layout transition; no looping spinner is the primary signal.

## 6. Screen 2 — Computed result

### Mobile order

1. Result statement
2. Savings and two route summaries
3. One comparison map
4. Scheduled timeline
5. Dropped-stop diagnostics when present
6. Handoff and share actions

### Mobile wireframe — 360px

```text
┌──────────────────────────────────┐
│ ← New day                vialo.  │
│                                  │
│ 6 stops fit 09:00–17:00          │
│ Venice · walking                 │
│                                  │
│ 38 min less walking              │
│ ┌──────────────────────────────┐ │
│ │ – – Naive   8.4 km · 1h 42 │ │
│ │     Misses a closing time    │ │
│ │ ━━━ Vialo   5.1 km · 1h 04 │ │
│ │     Fits 09:00–17:00         │ │
│ └──────────────────────────────┘ │
│                                  │
│ ┌──────────────────────────────┐ │
│ │                              │ │
│ │  one map · identical bounds │ │
│ │  coral dashed naive route   │ │
│ │  plum solid Vialo route     │ │
│ │  numbered place markers     │ │
│ │                              │ │
│ │  Google attribution visible │ │
│ └──────────────────────────────┘ │
│                                  │
│ Your schedule                    │
│ 09:00  01  Basilica             │
│             50 min · estimated  │
│ 09:50      Walk 6 min · 0.4 km │
│ 09:56  02  Palazzo              │
│             70 min · estimated  │
│ 11:06      Wait 14 min          │
│             Opens 11:20         │
│ ...                              │
│                                  │
│ Couldn't fit                    │
│ Arsenale · closes at 17:00      │
│                                  │
│ ┌──────────────────────────────┐ │
│ │ Open full route in Maps      │ │
│ └──────────────────────────────┘ │
│ [ Browser-safe route parts ]     │
│ [ Copy share link ]              │
│                                  │
│ Privacy · Terms · GitHub          │
└──────────────────────────────────┘
```

### Desktop layout

```text
┌────────────────────────────────────────────────────────────────────┐
│ ← New day                                                 vialo.  │
│                                                                    │
│ 6 stops fit 09:00–17:00 · Venice · walking                        │
│                                                                    │
│ 38 min less walking                                                │
│ [ – – Naive 8.4km · 1h42 · misses close ] [ ━ Vialo 5.1km · 1h04 ]│
│                                                                    │
│ ┌─────────────────────────────┐ ┌────────────────────────────────┐ │
│ │ Your schedule               │ │ one comparison map             │ │
│ │ 09:00 01 Basilica           │ │ both routes, same bounds       │ │
│ │ 09:50    Walk 6 min         │ │ active stop synchronized       │ │
│ │ 09:56 02 Palazzo            │ │ Google attribution unobscured │ │
│ │ ...                         │ │                                │ │
│ └─────────────────────────────┘ └────────────────────────────────┘ │
│                                                                    │
│ [ Open full route in Maps ] [ Copy share link ]                    │
└────────────────────────────────────────────────────────────────────┘
```

The result uses exactly one map. It proves the comparison and synchronizes with the timeline; a second map would add complexity without information.

## 7. Signature comparison — final decision

### Honest baseline

The naive baseline is the final retained stop set in Claude candidate order. It uses the same origin, destination/return rule, mode, and route options as the optimized order. Dropped stops are absent from both routes and shown separately.

### Four-second hierarchy

1. Savings headline: `38 min less walking` or `3.3 km less walking`.
2. Naive and Vialo metric summaries directly beneath it.
3. Overlay map using identical bounds.
4. Explicit feasibility labels.

### Encoding

| Route | Color | Stroke | Opacity | Label |
|---|---|---|---:|---|
| Naive | warm coral | 3px, 12px dash / 8px gap | 0.62 | `Naive order` |
| Vialo | deep plum | 5px solid | 1 | `Vialo order` |

Color is never the only distinction. Legends include text, stroke samples, and ordered stop sequences. Markers keep stable place numbers while legends show each route's order.

### Metrics

Metrics displayed in the comparison come from the paired ordered `computeRoutes` responses. If either real geometry response is unavailable, omit both lines and show a compact retryable comparison-unavailable state. Never draw straight segments.

Deltas are signed and never clamped or hidden. Choose the headline by evidence:

- Positive travel reduction: `38 min less walking` or `3.3 km less walking`.
- Naive infeasible and Vialo feasible: `Fits every closing time`; both summaries still show their real travel metrics, even if Vialo travels farther.
- Equal travel with less waiting: `14 min less waiting`.
- Identical multi-stop order: `Best order confirmed` with zero deltas.
- One retained stop: `One stop · no reordering needed`.
- A real route-total delta that contradicts the directed-matrix objective: neutral `Schedule-aware order` plus both signed metrics and a retryable comparison diagnostic; never claim savings.

When both orders are identical, render one shared plum solid geometry labeled `Same route` instead of hiding a dashed line beneath an identical solid line.

### Reveal

- 0–350ms: naive route draws.
- 250–750ms: Vialo route draws, overlapping the final 100ms of naive motion.
- 650–1050ms: savings metric counts once.
- By 1050ms: static comparison remains.

The reveal never replays on hover, resize, tab return, or map interaction. Identical-order results skip the two-line reveal and render the shared final geometry directly. Reduced-motion users receive the final state immediately.

## 8. Timeline and map synchronization

A single `activeStopId` controls both surfaces.

| Action | Timeline | Map |
|---|---|---|
| Hover/focus stop | warm soft highlight | marker gains ring and top stacking |
| Tap/click stop | expand bounded details | pan once and open compact label |
| Hover/focus marker | scroll row into nearest visible position | marker ring |
| Escape from details | collapse and restore row focus | retain map bounds |

No marker pulses or loops. Synchronization must not alter route visibility or map bounds used for comparison.

## 9. Scheduled timeline

- Arrival and departure remain visible in 24-hour tabular numerals.
- Travel rows show mode, real duration, and distance.
- Wait rows are distinct and explain the relevant opening time.
- Model durations say `estimated`; explicit user durations say `planned`.
- Opening annotations appear only when they explain a wait, close deadline, or dropped stop.
- Optional photos are subordinate and always carry every required linked author attribution.
- The layout remains complete with photos disabled.

## 10. Partial and infeasible states

A partial result leads with the valid schedule: `5 of 7 stops fit`. The exact retained set drives both comparison routes. Below the timeline, `Couldn't fit` lists every excluded or dropped stop with a factual template:

- `Closed on Tuesday`
- `Opening hours unavailable`
- `Closes at 17:00; earliest possible finish is 17:24`
- `No walking route was returned`

If no stop is feasible, do not show an empty map. Show the diagnostics and a primary `Adjust my request` action that returns focus to the populated input.

## 11. Handoff presentation

`Copy share link` is an explicit creation action: its first activation calls `POST /shares`, then copies the returned URL. Planning alone never stores a share. While creating, the control reports progress and prevents duplicate activation; an idempotent retry returns the same link.

When the full route is valid, the primary action is `Open full route in Google Maps`.

When mobile-browser waypoint limits apply, show a short supporting line and ordered part links below the full-route action. Do not silently send a shortened URL. If the full route is unavailable but parts are valid, the first part becomes primary and the interface states `Open route in 2 parts`.

If no handoff URL is valid, keep the Vialo map and timeline usable and state that Google Maps handoff is unavailable.

## 12. Screen 3 — Shared permalink

The shared route is read-only and uses the same result components and hierarchy.

```text
┌──────────────────────────────────┐
│ vialo.                           │
│ Shared itinerary · expires date │
│                                  │
│ 6 stops fit 09:00–17:00          │
│ [comparison metrics + one map]   │
│ [timeline]                       │
│ [dropped diagnostics]            │
│                                  │
│ This link is public to anyone    │
│ who has it.                      │
│                                  │
│ [ Open route in Google Maps ]    │
│ [ Build your own day ]            │
│                                  │
│ Privacy · Terms · GitHub          │
└──────────────────────────────────┘
```

An expired, missing, or deleted link displays `This itinerary is no longer available`, a short 30-day explanation, and `Build a new day`. It never confirms prior existence.

The share URL is public-by-link. Share creation stores its creator deletion token separately in browser-local state, never in the URL. Only a browser holding that token may see `Delete shared link`; deletion requires confirmation, clears the local token, and returns the generic unavailable state. Viewers who only know the public URL never receive a deletion control or capability.

## 13. Error states

| State | Message behavior | Action |
|---|---|---|
| Invalid input | specific inline correction | focus invalid input |
| Off-topic | brief scope statement | edit request |
| Rate limited | exact retry time | disabled until retry |
| Provider unavailable | no provider names or raw errors | retry |
| Comparison unavailable | schedule remains visible | retry comparison/request |
| Share unavailable | generic missing/expired state | build new day |

Use approved UI templates and typed parameters only. Errors never include raw API or model text.

## 14. Accessibility

- Semantic sections have visible headings; the timeline is an ordered list.
- Loading stage changes use a polite live region; result availability is announced once.
- Timeline rows are not all forced into the tab order unless they expose controls. Focusable controls inside rows receive descriptive names.
- The map has a textual alternative through route summaries and timeline; it is never the only source of information.
- Keyboard interaction does not trap focus in the map.
- Route identity uses color, stroke, weight, labels, and sequence.
- Reduced motion preserves all final information.
- Google controls/attribution, photo credits, footer links, and sticky actions remain unobscured at 360px.

## 15. Responsive acceptance

### 360px

- No horizontal scrolling.
- Comparison metrics stack before a map at least 280px high.
- Timeline uses a 52px time column and preserves complete schedule scanning.
- Touch targets are at least 44px.
- A sticky handoff action may appear only after a valid result and may not cover content or attribution.

### 768px

- Metric summaries may share one row.
- Timeline remains single-column unless the map can remain at least 360px wide.

### 1024px and above

- Timeline and the one map use a balanced 55/45 split.
- Comparison headline and summaries span both columns above them.
- Maximum content width is 1200px.

## 16. Component boundaries

```text
AppShell
├── InputHero
│   ├── PromptComposer
│   └── ExampleRequests
├── LoadingPipeline
├── ResultView
│   ├── ResultStatement
│   ├── RouteComparisonSummary
│   ├── ComparisonMap
│   ├── ScheduledTimeline
│   │   ├── TimelineStop
│   │   ├── TimelineTravel
│   │   └── TimelineWait
│   ├── DroppedStops
│   └── ResultActions
├── SharedItineraryView
├── PrivacyPage
├── TermsPage
└── SiteFooter
```

Components consume typed response data. Production result components do not contain embedded demonstration metrics or hard-coded itinerary objects.

## 17. Browser review gate

Before frontend acceptance, after runnable screens exist, the UI reviewer agent must collect Playwright evidence for:

- input default, focus, error, and loading at 360px;
- complete result and partial result at 360px and desktop;
- comparison after reveal and under reduced motion;
- keyboard path through input, result actions, timeline details, footer, and shared view;
- missing photo and multiple-attribution variants;
- Maps attribution and controls unobscured;
- long place names and maximum nine-stop timeline;
- expired shared permalink.

Findings are blockers, major issues, or polish. A visual pass requires screenshots plus accessibility snapshots, not narrative confidence.
