---
inclusion: always
---

# Product — Vialo

## What Vialo is

Vialo builds a day that actually fits. A user describes where they are, how much time they have, and what they want to see. Vialo returns a **scheduled itinerary** — up to 9 verified stops in the provably optimal order, with arrival and departure times that respect each place's real opening hours — and hands it off to Google Maps as a ready-to-navigate route.

**Vialo is a constraint solver for one day in a city.** It is not a trip planner, not an AI assistant, and not a maps-link generator. The Google Maps link is the last mile of delivery, not the product itself.

## Who it's for

A person standing on a street in an unfamiliar city with limited time, wanting to see the best things without wasting that time on logistics. The interface is mobile-first because the user is already there.

## The problem, concretely

Planning a day of sightseeing by hand means: ask a chatbot what to see, Google each place individually, paste them into Google Maps one at a time, drag the pins around trying to avoid zigzags, and hope nothing is closed when you arrive. That process takes 30–60 minutes and still produces broken results — wrong orders, closed doors, days that don't fit.

Any chatbot can emit a Google Maps URL. That was tested and confirmed. The link is trivial. What's hard is making the *content* of that link correct.

## Three things a chatbot structurally cannot do

1. **Ground the places.** LLM-generated coordinates are hallucinated — confident, well-formed, wrong by 50–300 meters. Google Maps will route you to a canal. Vialo resolves every stop to a real `place_id`: real door, real address, real photo.

2. **Optimize the order.** A language model guesses a plausible sequence. Vialo computes a real travel-time matrix from the Google Routes API and solves it exactly — provably shortest, not plausible-looking.

3. **Make the day fit.** Explicit visit-duration estimates + real opening hours + real travel times = a schedule that either works or gets explicitly diagnosed. "This is 6.5 hours of walking; you have 5 — here's what I cut, and here's why stop 7 moved earlier." A chatbot silently produces a broken day and confidently tells you it's fine.

## Frozen scope — 5 features, nothing else

1. **Prompt → grounded, scheduled itinerary.** Places-verified stops, opening hours respected, infeasible days diagnosed rather than silently broken.
2. **Exact route optimization with a visible naive-vs-optimized comparison.** The single highest-leverage element — it answers "why not just ask ChatGPT?" visually in four seconds.
3. **Timeline view + map preview.** Arrival/departure times, walking legs, "opens 09:30" annotations. This is what makes Vialo visibly different from a chat response.
4. **Open in Google Maps + anonymous share permalinks.** `vialo.place/r/<id>`, readable with no account and no sign-up.
5. **Vialo Journal.** Travellers publish what a day in a city was actually like, optionally attaching the itinerary Vialo computed for them. Reading is anonymous; publishing, commenting, and reporting need an account. Specified in [`../specs/journal/`](../specs/journal/).

If something would improve the product but isn't in this list, it goes in the README's "Future" section. It does not get built. Scope creep is the most likely way this project fails to ship.

**Amendment, 2026-08-20.** This list said 4 features until the Journal shipped. The count changed because the product needed a reason for a traveller to come back after their day was planned, and a route nobody else ever sees is a dead end. Recording the amendment here, with its date, is the point: the scope freeze is a real constraint, so widening it is an event rather than an edit. The Journal is the only feature in this repository whose specification was written after its code, which is recorded in `KIRO.md` rather than smoothed over.

## Language discipline

- The phrase "trip planner" must never appear in the title, tagline, README, UI copy, code comments, or commit messages.
- Never describe Vialo as an "AI assistant" or "AI-powered planning tool."
- The Google Maps link is always referred to as the last mile, the handoff, the delivery mechanism — never the product.
- ❌ "AI-powered trip planning assistant"
- ✅ "Describe your day. Get one that actually fits."

## Non-negotiable principles

- **Nothing simulated.** No hard-coded results presented as working features, no mock data standing in for a real integration. A judge running the app must get genuinely computed output. This is pass/fail in Round One.
- **Zero learning curve.** A judge lands on it, understands it in 5 seconds, gets value in 30.
- **Free during judging.** No payment, ever. Planning a day needs no account and never will: a judge lands on the site and gets a computed itinerary without signing up for anything. Publishing to the Journal is the single exception, because attributing written content to a person is the whole point of it. Amended 2026-08-20; this principle read "No accounts, no payment" until the Journal shipped.
- **Accounts hold as little as possible.** Identity lives in Cognito. The Journal table stores an opaque subject and a display name, never an email address. No profile pages, no follows, no notifications.
- **Maximum 9 visit stops.** This keeps the fixed-origin exact solver bounded at 9! and the directed matrix at 10×10. Google Maps platform-specific waypoint limits are handled explicitly with a full URL plus browser-safe route parts—never by silently dropping stops.
- **English only** in all code, docs, and UI.
- **No real API keys, secrets, or credentials in any committed file.** This is a disqualification trigger.
