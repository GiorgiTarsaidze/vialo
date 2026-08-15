---
name: mobile-ux-audit
description: Audit Vialo's core flow at narrow viewports for scanability, touch use, responsive order, and low cognitive load. Use whenever mobile layouts or interactions change.
---

# Mobile UX audit

## Required viewport

Begin at 360 px wide. Also inspect 390 px and a narrow landscape or tablet width when the implementation exists.

## Checks

- No horizontal scrolling, clipped route labels, or map controls outside the viewport.
- One obvious primary action per state; touch targets are at least 44 by 44 px.
- Result order is comparison, timeline, map, then handoff actions.
- The full schedule remains scannable and is not hidden in default accordions.
- Arrival/departure times retain a stable compact column; travel legs remain readable.
- Sticky actions do not cover content, Google attribution, focused controls, or error messages.
- Loading, infeasible, partial, and error states preserve layout stability and offer a clear next action.
- Keyboard focus remains visible and follows the visual order.
- Text never drops below the design-system minimum, and long place names wrap without breaking alignment.

Use browser resizing, screenshots, and accessibility snapshots when available. Report the exact viewport and interaction that demonstrates each issue.
