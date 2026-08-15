---
name: accessibility-review
description: Review Vialo for WCAG AA contrast, semantic structure, keyboard operation, focus visibility, motion preferences, and non-color communication. Use during component and full-page review.
---

# Accessibility review

## Visual and semantic checks

- Body copy, muted text, controls, and route labels meet WCAG AA contrast in every state.
- Pastel colors are supporting surfaces, never the sole carrier of status or route identity.
- Heading levels describe the page hierarchy; landmarks and accessible names make the flow understandable from an accessibility snapshot.
- Every interactive control is reachable and operable by keyboard with a visible focus ring.
- Focus order follows visual order and is restored sensibly after dialogs, errors, or async results.
- Form labels, errors, loading status, and infeasibility diagnostics are announced clearly.
- Icons have text labels where meaning is not decorative.
- Maps have a meaningful textual route and timeline alternative.
- Place-photo credits are readable links, and Google attribution remains visible.
- `prefers-reduced-motion` removes route drawing, counting, and stagger effects without removing information.

Use accessibility snapshots plus keyboard traversal; screenshots alone are insufficient. Report blockers before visual polish findings.
