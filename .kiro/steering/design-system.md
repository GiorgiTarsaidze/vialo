---
inclusion: always
---

# Design System — Vialo

## Design intent

Vialo should feel like a beautifully edited city guide combined with a precise scheduling instrument: warm, calm, geographic, and trustworthy. It must not look like a chat interface, an enterprise dashboard, or a generic travel marketplace.

The interface has two visual voices:

- **Editorial warmth** for the invitation to describe the day and for place imagery.
- **Operational precision** for times, route metrics, opening hours, and feasibility.

The result should communicate its value before the user reads explanatory copy. On the result screen, the route comparison proves optimization and the timeline proves scheduling.

## Experience principles

1. **The schedule is the product.** Give the timeline and route comparison more visual weight than prose, controls, or decorative imagery.
2. **Evidence over claims.** Show verified places, actual hours, route geometry, and measured savings instead of saying the result is intelligent.
3. **Progressive disclosure.** The first scan shows the answer; secondary place details appear only when requested.
4. **Mobile first.** Every primary action and all itinerary information must work at 360 px without horizontal scrolling.
5. **Calm density.** Fit a useful day on screen without making it feel crowded. Use rhythm, alignment, and typography rather than excessive cards.
6. **Accessible by construction.** Meet WCAG AA contrast, preserve visible focus states, support keyboard navigation, and never rely on color alone.

## Visual direction

### Character

- A luminous warm-cream canvas with clean white working surfaces
- Warm charcoal ink for clarity; never brown body copy or low-contrast pastel text
- Deep warm plum as the primary action and optimized-route color
- Warm coral as the naive-route color
- Pastel butter yellow, blush pink, and soft lilac used as quiet supporting fields, never as a rainbow
- Fine warm borders, restrained shadows, and generous corner radii
- Place photography used as evidence, not as full-screen decoration
- Route lines, time rails, and compact numeric labels create the geographic/scheduling identity

Aim for roughly 80% cream/white foundations, 10% dark ink and plum structure, and 10% pastel emphasis. Visual impact comes from composition, the route reveal, confident scale, and operational precision—not from adding controls or decoration.

Avoid gradients, glassmorphism, neon colors, cool corporate blues, oversized dashboard cards, chat bubbles, and decorative map-pin clichés.

### Typography

Use a self-hosted, open-license pairing so production does not depend on a third-party font request:

- **Display:** `Newsreader`, Georgia, serif — editorial headlines and the short result statement only
- **UI:** `Inter`, system-ui, sans-serif — controls, body text, place names, and labels
- **Numeric:** use Inter with `font-variant-numeric: tabular-nums` for all times, distances, and durations

Document and attribute the font licenses in the README when the font files are added.

### Type scale

| Token | Size / line height | Weight | Use |
|---|---:|---:|---|
| `display-xl` | 48 / 52 px | 500 | Desktop hero only |
| `display-lg` | 38 / 42 px | 500 | Mobile hero, result statement |
| `heading-lg` | 28 / 34 px | 600 | Major result sections |
| `heading-md` | 22 / 28 px | 600 | Comparison headline, stop name |
| `heading-sm` | 18 / 24 px | 600 | Card and subsection headings |
| `body-lg` | 17 / 27 px | 400 | Introductory copy |
| `body` | 15 / 23 px | 400 | Default body and itinerary details |
| `label` | 13 / 18 px | 600 | Controls and compact metadata |
| `caption` | 12 / 16 px | 500 | Opening annotations and supporting labels |

On screens below 640 px, reduce `display-xl` to `display-lg`; do not reduce body text below 15 px.

## Color tokens

```css
:root {
  --color-canvas: #fff8ea;
  --color-surface: #fffcf5;
  --color-surface-strong: #ffffff;
  --color-ink: #2b2326;
  --color-ink-muted: #6d6064;
  --color-border: #e7d8d1;
  --color-border-strong: #bfaaa4;

  --color-primary: #6f3e59;
  --color-primary-hover: #593047;
  --color-primary-soft: #f2e2ea;

  --color-accent-sun: #d89b2b;
  --color-accent-sun-soft: #fff0c2;
  --color-accent-blush: #f8e3e7;
  --color-accent-lilac: #eee6f2;

  --color-naive: #a95242;
  --color-naive-soft: #f7e2da;
  --color-optimized: #6f3e59;
  --color-optimized-soft: #f2e2ea;

  --color-warning: #8a5b00;
  --color-warning-soft: #fff0c2;
  --color-danger: #9a3f50;
  --color-danger-soft: #f8dde4;
  --color-success: #456a50;
  --color-focus: #6a4fa3;

  --color-map-land: #f4ebdd;
  --color-map-water: #e7e1f2;
  --color-map-road: #ffffff;
}
```

Rules:

- Body text uses `ink`; secondary text uses `ink-muted` only at AA-compliant sizes.
- Primary actions and the optimized route use deep plum consistently.
- Butter, blush, and lilac are background emphasis only. Never place muted or white body text directly on these fills without a verified AA contrast pair.
- Use at most two supporting pastel families in one viewport so the interface remains composed rather than playful or busy.
- The naive route uses warm coral, a dashed line, and an explicit label; the optimized route uses plum, a solid line, and a heavier stroke. Color is never the only distinction.
- Warning and danger colors are reserved for infeasibility and errors, not decoration.
- Google Maps attribution and controls must remain visible and unobscured.

## Spacing, shape, and elevation

### Spacing scale

Use a 4 px base unit:

| Token | Value |
|---|---:|
| `space-1` | 4 px |
| `space-2` | 8 px |
| `space-3` | 12 px |
| `space-4` | 16 px |
| `space-5` | 24 px |
| `space-6` | 32 px |
| `space-7` | 48 px |
| `space-8` | 64 px |
| `space-9` | 96 px |

Use 16 px mobile page gutters, 24–32 px tablet gutters, and a centered 1200 px maximum content width. Major result sections use 48–64 px vertical separation; internal card spacing uses 16–24 px.

### Shape

- Input and primary buttons: 14 px radius
- Cards and map containers: 18 px radius
- Pills and compact status labels: full radius
- Route lines and timeline rails: round caps
- Borders: 1 px; use 2 px only for selected or focused states

### Elevation

Prefer borders over shadows. Use one restrained floating elevation only for the prompt composer or sticky mobile action:

```css
--shadow-floating: 0 12px 32px rgb(43 35 38 / 0.12);
```

## Layout rules

### Input hero

- One prominent natural-language field, one primary submit action, and up to three one-click examples.
- The headline explains the outcome, not the technology: “Describe your day. Get one that actually fits.”
- Do not use chat bubbles, message history, an avatar, or typing-assistant language.
- Keep model and pipeline details out of the first viewport.

### Result hierarchy

1. Short result statement: number of stops, time window, and feasibility
2. Naive-vs-optimized route comparison
3. Scheduled timeline and map preview
4. Dropped-stop or constraint diagnostics, when applicable
5. Open in Google Maps and share actions

On desktop, timeline and map may sit in a balanced two-column layout. On mobile, the comparison comes first, then timeline, then map. The Google Maps action may be sticky at the bottom after a valid result exists.

## Signature surface 1 — scheduled timeline

The timeline must look like a schedule, not a list of recommendations.

### Anatomy of a stop

Each stop row contains:

- **Left time column:** arrival and departure in tabular numerals, aligned vertically
- **Timeline rail:** numbered stop marker connected to the previous and next legs
- **Primary content:** verified place name and visit duration
- **Evidence:** compact address and optional place photo
- **Constraint annotation:** opening information when it explains the schedule, such as `opens 09:30` or `closes 18:00`

Example information order:

```text
09:40  01  Basilica di San Marco        50 min
           Opens 09:30 · Piazza San Marco
10:30      Walk 6 min · 0.4 km
10:36  02  Palazzo Ducale               70 min
```

### Timeline rules

- Times are the strongest repeated visual anchor. Use 24-hour format and tabular numerals.
- Arrival is primary; departure is visible but quieter. Never hide either in a tooltip.
- Walking/driving legs are first-class rows between stops, not footnotes. Show mode, duration, and distance.
- Opening-hours annotations appear only when useful: the first opening boundary, a wait caused by opening time, a close deadline, or an infeasibility reason. Do not repeat ordinary hours under every stop.
- If arrival precedes opening, show a distinct waiting segment and include that wait in the schedule.
- A stop affected by a time constraint receives a small clock icon plus text. Icons never replace labels.
- Dropped stops never disappear silently. Show a separate “Couldn’t fit” section with a plain-language reason grounded in time or opening-hour data.
- Place photos are optional and subordinate. Missing photos must not break row height or alignment.
- When a Places photo is shown, render its returned author attribution in a readable linked credit; never strip or obscure attribution data.
- Label visit duration as estimated in the stop's supporting metadata without weakening the primary time hierarchy.
- The active stop may highlight both its timeline marker and map pin. Hover, focus, and tap states must stay synchronized.
- Keep the timeline readable with photos disabled; its structure comes from type, spacing, and the time rail.

### Responsive behavior

- Under 480 px, use a 52 px time column and place the timeline rail immediately beside it.
- Keep leg rows compact but at least 44 px high when interactive.
- Never collapse the full schedule into an accordion by default. The user should be able to scan the entire day.

## Signature surface 2 — naive vs optimized route comparison

This is the centerpiece of the result and the highest-leverage explanation of Vialo. A judge must understand the benefit in approximately four seconds without reading supporting prose.

### Honest baseline

The naive baseline is the grounded candidate stops in the order returned before route optimization. It uses the same stops, origin, destination/return rule, travel mode, and Routes API matrix as the optimized result. Never compare different stop sets or fabricated values. If the naive order violates hours or the time budget, say so explicitly.

### Required content

- A direct outcome headline: `3.3 km less walking` or `38 min saved`
- Two immediately comparable summaries:
  - `Naive order — 8.4 km · 1 hr 42 min walking`
  - `Vialo order — 5.1 km · 1 hr 04 min walking`
- One map showing both routes over the same bounds:
  - Naive: warm coral, 3 px dashed line, lower opacity
  - Optimized: deep plum, 5 px solid line, full opacity
- Matching labeled legends and metrics; do not rely on route color alone
- A compact feasibility badge when relevant: `Misses closing time` versus `Fits 09:00–19:00`

### Composition

- Place the savings headline above the map, not inside it.
- Give the optimized result greater weight, but keep the baseline legible enough to verify the comparison.
- On desktop, place the metric summaries beside or above a wide map. On mobile, stack the summaries above a map at least 280 px tall.
- Both routes must use identical map bounds and scale.
- Stop markers use the same numbers in both orders; selected-route sequence is communicated by line direction and a compact ordered legend.
- Do not animate route changes in a way that makes direct comparison impossible. Both routes remain visible after the reveal.

### Reveal motion

1. Draw the naive route first in 350 ms.
2. Draw the optimized route in 500 ms.
3. Count the savings metric once over 400 ms.
4. Settle into a static, directly comparable state.

The full reveal finishes in under 1.2 seconds. With `prefers-reduced-motion: reduce`, render the final state immediately.

## Motion principles

Motion explains state and hierarchy; it never decorates waiting.

- **Fast feedback:** 120–180 ms for hover, focus, press, and toggles
- **Section transitions:** 240–360 ms, ease-out
- **Result arrival:** stagger comparison, timeline, then actions over no more than 700 ms
- **Map route reveal:** defined above; play once only
- **Loading:** narrate real pipeline stages — finding places, checking opening hours, measuring travel, optimizing the route — without fake percentages
- **No perpetual motion:** no pulsing map pins, looping route draws, bouncing buttons, or autoplay carousels
- Honor `prefers-reduced-motion` and preserve all information without animation

## Components and interaction states

Every interactive component must define: default, hover, active, focus-visible, disabled, loading, and error states.

- Minimum touch target: 44 × 44 px
- Visible focus ring: 2 px `focus` with 2 px offset
- Primary action: deep plum fill, white label
- Secondary action: surface fill, strong border, ink label
- Links are underlined in prose; navigation/action links may use a clear icon plus text
- Loading skeletons must match the eventual layout to prevent jumps
- Errors use a concise explanation and a next action; never expose raw API or stack-trace text

## Copy and data presentation

- Use short, factual labels: `Walk 6 min`, `Opens 09:30`, `38 min saved`.
- Avoid anthropomorphic copy such as “I planned” or “I think.”
- Avoid hype such as “magical,” “perfect AI,” or “revolutionary.”
- Never expose model-generated prose. All displayed data comes from typed fields and approved UI templates.
- Distances use kilometers and meters; durations use human-readable hours/minutes; times use the place's local timezone.
- State when data is unavailable instead of inventing a value.
