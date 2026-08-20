# How Vialo was built with Kiro

Vialo is a constraint solver for one day in a city. This document is about the other half of the
project: the Kiro workflow that produced it, what that workflow got right, and where it had to be
corrected. Every claim here points at a committed artifact or a command you can re-run.

- Steering: [`.kiro/steering/`](.kiro/steering/) — 4 files, 661 lines
- Specs: [`.kiro/specs/`](.kiro/specs/) — the itinerary engine (13 requirements, a 578-line design, 21 tasks in 6 waves), a 394-line frontend blueprint, and the Journal (11 requirements, 18 tasks), the last of which was written after its code and says so
- Agents: [`.kiro/agents/`](.kiro/agents/) — `ui-reviewer`, `backend-engineer`
- Hooks: [`.kiro/hooks/`](.kiro/hooks/) — repository, frontend, and backend validation
- Skills: [`.kiro/skills/`](.kiro/skills/) — 5 progressive review skills
- MCP: [`.kiro/settings/mcp.json`](.kiro/settings/mcp.json) — Playwright pinned to `@playwright/mcp@0.0.79`
- Evidence: [`docs/kiro-evidence/`](docs/kiro-evidence/)

## The order of the commit history is the argument

```
b0ff0c7  chore: add repository ignore rules          <- .gitignore first, before any code
59ee635  docs: establish Vialo project foundation    <- steering
8ba7c22  test: add validated Google API fixtures     <- real provider responses before speccing
fbe0352  feat: add Kiro visual review tooling        <- agent, skills, hooks, MCP
59e43fb  docs: complete pre-build Kiro specifications<- requirements, design, tasks
0bf0812  docs: switch backend architecture to Python <- correction made in the spec, not in code
3a3f0da  feat: ship Phase 3 Python backend           <- first application code
5a66692  feat: migrate Vialo inference to Bedrock
77c8a55  feat: ship React frontend and secure CloudFront hosting
3230047  feat: add structured routing and polish itinerary UX
acffec1  Improve itinerary resilience and refresh UI
```

Nothing was written before the steering existed, and no application code was written before the
requirements, design, and task graph existed. The architecture change in `0bf0812` is the clearest
example: the first design inherited a TypeScript Lambda assumption from early steering, and that
was corrected in the spec **before** any backend code was generated, not refactored afterwards.

## Steering: the highest-leverage hour of the project

Four always-loaded files carry the decisions that everything else inherits:

| File | What it constrains |
|---|---|
| `product.md` | What Vialo is and is not, the frozen 4-feature scope, and language discipline — the phrase "trip planner" is banned in code, docs, and UI copy |
| `tech.md` | The 5-step pipeline, why brute force instead of a heuristic, and 11 non-negotiable security rules |
| `structure.md` | Layout, naming, dependency policy, testing policy, and the exact set of environment variables |
| `design-system.md` | Colour tokens, type scale, spacing, motion, and the anatomy of the two signature surfaces |

The value shows up as things that *did not happen*. Because `product.md` forbids the phrase and
`tech.md` forbids rendering model prose, no generated component ever shipped a chat bubble or a
model-authored sentence. Because `structure.md` states that domain modules must not import Google,
boto3, or Powertools, `backend/src/vialo/domain/` is still provider-free and directly unit-testable.

Two steering rules were written specifically to stop plausible-sounding but false claims:

- Visit durations must be labelled estimates. The recorded Places fixture has no typical-duration
  field, so the response model carries an explicit `durationSource` of `user` or `model_estimate`.
- Solver latency must be benchmarked, never asserted. That rule is what eventually produced the
  measurement in the last section of this document.

## Specs: 13 requirements → 21 tasks → the shipped module tree

[`.kiro/specs/itinerary-engine/`](.kiro/specs/itinerary-engine/) is the backend contract:
`requirements.md` (13 numbered requirements with acceptance criteria and stable diagnostic codes),
`design.md` (pipeline, error handling, cache freshness, and the justification for exhaustive
search), and `tasks.md` (21 tasks grouped into 6 waves, each task annotated with the requirements
it satisfies and whether it can run in parallel).

The task list maps almost one-to-one onto the files that exist today — task 11 "implement exact
permutation scheduling" is `domain/solver.py`, task 12 is `domain/dropping.py`, task 16 is
`domain/maps_url.py`. That correspondence is why the spec is worth reading: it is not a document
written next to the code, it is the document the code was generated from.

Frontend work used [`.kiro/specs/frontend-experience/blueprint.md`](.kiro/specs/frontend-experience/blueprint.md)
instead of a second full spec: a screen-by-screen blueprint with acceptance behaviour for
responsive, keyboard, reduced-motion, loading, partial, infeasible, error, and expired-share
states. Reviewing those states before implementation is why the deployed app has typed error
screens rather than raw stack traces.

## Agents, hooks, and skills

Two project-local agents, each with narrow write paths and its own validation hook:

- **`ui-reviewer`** — design and review, with the pinned Playwright MCP server bound directly in
  the agent config. Its `stop` hook runs frontend lint and typecheck.
- **`backend-engineer`** — engine work against the spec, with write access limited to
  `backend/`, `infra/`, `scripts/`, `docs/`, and `.kiro/specs/`. Its `stop` hook runs Ruff, Ruff
  format, strict mypy, and the full pytest suite, so a turn cannot end with a red gate.

Both agents run `.kiro/hooks/validate-repository.sh` after every write. That hook is the reason a
credential cannot reach a commit by accident: it fails on tracked or untracked files matching
Google, Anthropic, AWS, GitHub, or private-key patterns, and on any tracked file under the ignored
`.tmp/` planning directory. Transcripts of all three hooks are in
[`docs/kiro-evidence/hook-runs.txt`](docs/kiro-evidence/hook-runs.txt).

Five [skills](.kiro/skills/) load progressively rather than always: visual review, mobile UX audit,
route-comparison review, accessibility review, and judge-first-impression. Keeping them as skills
rather than steering is deliberate — a route-comparison checklist should not consume context while
someone is editing the opening-hours normalizer.

## Where Kiro was wrong, and what fixed it

The honest entries are the useful ones. Each of these was a real defect caught by review, by a
hook, by a test, or by a live call — not a hypothetical.

| Problem | Root cause | Fix |
|---|---|---|
| Steering claimed Places returns a typical visit duration | Plausible assumption never checked against the API | Captured a real `searchText` response first; duration became an explicitly bounded, explicitly labelled estimate |
| Design specified a TypeScript Lambda | Early steering artefact carried into `design.md` | Rewrote the architecture in the spec before any code existed (`0bf0812`) |
| Travel matrix sized 9×9 | Forgot the fixed origin is a matrix point | Corrected to 10×10 = 100 directed elements in requirements and design |
| Custom agent started with no browser tools | Workspace MCP config is not inherited by a custom agent | Bound the pinned Playwright server inside the agent config; a second startup exposed 23 browser tools |
| Considered using `KIRO_API_KEY` for production inference | Assumed Kiro credentials could fund deployed model calls | Checked the documentation: it authenticates headless CLI sessions only. Production uses Bedrock with IAM, and `KIRO_API_KEY` is explicitly absent from `.env.example` |
| Model emitted `index` instead of `candidate_index` | Prompt contract was ambiguous | Made the exact key mandatory in both the initial and repair instructions, with a regression test |
| `computeRoutes` rejected walking requests | `routingPreference` is invalid for `WALK` and `BICYCLE` | Omit it for walking, send `TRAFFIC_UNAWARE` only for driving, and assert the request body in tests |
| `Hotel Danieli, Venice` scored worse than a wrong result | Locality tokens polluted place-name similarity | Separated canonical-name coverage from address qualifiers while keeping ambiguity rejection |
| Share creation returned 400 for valid itineraries | Strict Pydantic validated already-decoded JSON in Python mode | Route now uses `model_validate_json`, with a round-trip regression |
| A concurrency test flaked | Moto's in-memory backend can lose concurrent writes that real DynamoDB serialises per item | Kept genuinely concurrent callers, serialised only the emulated storage, still evaluated the production condition; passed 20 consecutive stress runs |
| A real Tbilisi prompt was refused as off-topic | Scope-guard vocabulary was too narrow | Broadened travel and place vocabulary instead of adding a city allow-list; dining-only and time-only prompts still refuse |
| Date-less prompts could schedule a day that already started | Missing rule for an elapsed local window | Roll to the next upcoming local start in the origin timezone; explicit dates are preserved |
| Model-authored strings had no length bound | Only the *shape* of model output was constrained, not the size of displayed strings | Bounded `locality_query`, `origin_query`, and candidate names, since a dropped-stop name is rendered and can persist in a share |
| `MemorySize: 512` was never justified | `tech.md` demanded benchmark evidence that did not exist yet | Benchmarked the real solver in a real ARM64 Lambda and raised memory to 1769 MB (below) |
| The naive route was invisible on the comparison map | Both polylines were drawn, but the thin dashed baseline went under a 5 px solid line on largely the same streets — generated code satisfied the spec's *content* rules without anyone checking the result on screen | Moved polyline options into a pure, unit-tested module; the baseline now draws above the optimized route with a real dash pattern while the optimized line keeps the heavier solid stroke |
| Routing waypoints were sent as raw coordinates | The pipeline already held a verified `place_id` for every stop and threw it away at routing time, so Google snapped each point to the nearest routable edge, often a car road | Both `computeRouteMatrix` and `computeRoutes` now send `placeId` waypoints, which fixes the measured durations and not just the drawn line |
| A four-hour day could return one stop and a red "couldn't fit" box | Nothing in the pipeline ever asked for *new* ideas when candidates died in grounding; the day just got thinner | Added a target density, reserve candidates in the same selector call, and one bounded top-up call; the red box became a neutral "also worth seeing" section |
| A hidden story still served its comment thread | `list_comments` never resolved the story, so three reports hid the post at `404` while `GET .../comments` kept returning `200` with the whole discussion | The comments route now resolves the story first, which already excludes hidden ones; found by probing the deployed API rather than by a test, and closed with two regression tests |
| **The Journal shipped without a spec** | Steering froze scope at four features, so there was no spec slot for a fifth, and the feature was built directly from a questionnaire under deadline pressure | Wrote [`.kiro/specs/journal/`](.kiro/specs/journal/) afterwards and labelled all three files as written after the implementation, then amended `product.md` to five features with the date and the reason. See below |

## The one place this workflow broke its own rule

The claim at the top of this document is that no application code was written before a spec existed.
That is true of everything except the Journal, and the exception is worth stating plainly rather than
quietly leaving the reader to notice.

The Journal was built from a 15-question design questionnaire answered in a single sitting, straight
into code, in roughly the last day of the build. The mechanism that let it happen is visible in the
steering itself: `product.md` froze scope at four features and said "no accounts, no sign-up", so a
fifth feature had nowhere legitimate to go. Under deadline pressure the code was written first and
the constraint was left contradicting it.

What was done about it:

- [`.kiro/specs/journal/`](.kiro/specs/journal/) now exists, with requirements, design, and tasks
  reconstructed by reading the shipped code. All three files carry a provenance note saying they were
  written after the implementation. The checkboxes in `tasks.md` record what exists, not what was
  planned.
- `product.md` moved from four features to five, and the "no accounts, no payment" principle was
  amended rather than rewritten: both changes carry their date and their reason inline.
- The Privacy page was corrected. It had said Vialo "does not create accounts or collect personal
  information" while a Cognito user pool was live in production, which was simply false.

The reason for handling it this way rather than backdating a spec: a specification whose only purpose
is to make a process claim look clean is worth less than no specification at all. The itinerary engine
demonstrates the discipline; the Journal demonstrates what happens without it, and both are more
useful on the record than one of them quietly edited.

## The benchmark that closed the last open task

`tech.md` said to start at 512 MB and change memory only from 8!/9! benchmark evidence. Task 13 of
the spec stayed unchecked for that reason. [`scripts/solver_benchmark.py`](scripts/solver_benchmark.py)
closes it by running the production `solve_exact` and `solve_route` functions over a fixed-seed
directed matrix, both locally and inside a throwaway ARM64 Lambda built from the deployed
dependency layer.

Worst case per request is the `dropping` case: nine stops that cannot fit, so the exhaustive search
runs again after each progressive drop.

| Environment | 8! dropping | 9! exhaustive (all feasible) | 9! dropping |
|---|---:|---:|---:|
| Lambda ARM64, 512 MB | 1.34 s | 11.66 s | 11.98 s |
| Lambda ARM64, 1024 MB | 0.64 s | 5.50 s | 5.76 s |
| Lambda ARM64, 1769 MB | 0.40 s | 3.39 s | 3.53 s |

Observed non-solver request time on the deployed function already reaches 19.6 s (Bedrock,
grounding, matrix, two geometry calls, cold start) inside a 30 s API Gateway budget. Twelve seconds
of solving on top of that would have timed out a full nine-stop day. Raising memory to 1769 MB —
one full vCPU — keeps the search provably optimal instead of trading it for a heuristic, and Lambda
GB-seconds stay roughly flat because the duration falls by about the same factor the price rises.

Raw results: [`docs/kiro-evidence/solver-benchmark/`](docs/kiro-evidence/solver-benchmark/).

## Reproducing the Kiro-side claims

```bash
# agent configs are valid and hooks execute
kiro-cli agent validate --path .kiro/agents/backend-engineer.json
kiro-cli agent validate --path .kiro/agents/ui-reviewer.json
.kiro/hooks/validate-repository.sh
.kiro/hooks/validate-backend.sh
.kiro/hooks/validate-frontend.sh

# zero-spend guardrail battery and the deployed solver benchmark harness
uv run --project backend python scripts/scope_guard_battery.py
uv run --project backend python scripts/solver_benchmark.py --stops 8 9 --repeats 5

# no credentials anywhere in history
docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source=/repo --redact
```

## What this workflow did not include

No screen recordings of steering being written or of task waves executing were captured while they
happened. Producing them now would be a re-enactment, so the Kiro story here rests on artifacts
instead: the committed `.kiro/` tree, a task list that matches the shipped modules, hook
transcripts, and a correction log where each entry names the commit that resolved it. See
[`docs/kiro-evidence/README.md`](docs/kiro-evidence/README.md) for the full index and
[`DEVLOG.md`](DEVLOG.md) for the day-by-day record.
