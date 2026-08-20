---
inclusion: always
---

# Structure — Vialo

## Repository layout

```text
vialo/
├── .kiro/
│   ├── agents/             # project-local specialist agents
│   ├── hooks/              # executable validation automation
│   ├── settings/           # workspace MCP configuration
│   ├── skills/             # progressive visual, mobile, route, and accessibility guidance
│   ├── specs/
│   │   ├── itinerary-engine/    # backend requirements.md, design.md, tasks.md
│   │   └── frontend-experience/ # agent-led screen blueprint
│   └── steering/           # product.md, tech.md, structure.md, design-system.md
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── favicon.svg
│   ├── src/
│   │   ├── components/     # React components, one per file
│   │   ├── hooks/          # custom React hooks
│   │   ├── lib/            # API client and generated/validated contracts
│   │   ├── styles/         # global CSS and design tokens
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/              # component tests or colocated *.test.tsx files
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/
│   ├── src/
│   │   └── vialo/
│   │       ├── __init__.py
│   │       ├── handler.py             # Lambda Powertools API Gateway entry point
│   │       ├── api/
│   │       │   ├── itineraries.py     # planning route
│   │       │   └── shares.py          # create/read/delete share routes
│   │       ├── pipeline/
│   │       │   ├── select_stops.py
│   │       │   ├── ground_places.py
│   │       │   ├── compute_matrix.py
│   │       │   ├── solve_route.py
│   │       │   ├── compute_route_geometry.py
│   │       │   └── build_maps_handoff.py
│   │       ├── services/
│   │       │   ├── candidate_selector.py   # provider-neutral Protocol
│   │       │   ├── bedrock_selector.py      # production Bedrock Claude adapter
│   │       │   ├── places_client.py        # direct Google REST wrapper
│   │       │   ├── routes_client.py        # direct Google REST wrapper
│   │       │   ├── place_cache.py
│   │       │   ├── rate_limiter.py
│   │       │   └── share_repository.py
│   │       ├── models/                 # strict Pydantic request/provider/response models
│   │       │   ├── requests.py
│   │       │   ├── providers.py
│   │       │   ├── itinerary.py
│   │       │   └── diagnostics.py
│   │       └── domain/                 # provider-free deterministic logic
│   │           ├── opening_hours.py
│   │           ├── route_matrix.py
│   │           ├── solver.py
│   │           └── timezones.py
│   ├── tests/
│   │   ├── unit/                       # pure logic and property tests
│   │   ├── integration/                # mocked provider and DynamoDB boundaries
│   │   └── contract/                   # API schema and frontend compatibility tests
│   ├── pyproject.toml
│   └── uv.lock
├── infra/
│   └── template.yaml       # AWS SAM: HTTP API, Lambda, DynamoDB, logs, S3/CloudFront
├── docs/
│   ├── api-samples/        # canonical sanitized provider responses
│   └── kiro-evidence/      # screenshots and recordings (large raw files ignored)
├── DEVLOG.md
├── KIRO.md
├── README.md
├── LICENSE
├── .env.example            # required configuration placeholders, never real values
└── .gitignore
```

## Language and naming conventions

### Python backend

- Runtime: Python 3.12.
- Modules and functions: `snake_case` (`solve_route.py`, `build_maps_handoff`).
- Classes, protocols, and Pydantic models: `PascalCase` (`ItineraryResponse`, `CandidateSelector`).
- Constants and environment variables: `UPPER_SNAKE_CASE` (`MAX_STOPS`, `CACHE_TTL_SECONDS`).
- Tests: `test_<module>.py`; test functions describe behavior in `snake_case`.
- Imports: absolute imports from `vialo`; no wildcard imports and no import-side-effect registration outside the API composition root.
- Domain modules do not import Google, boto3, Lambda Powertools, or API Gateway types.

### TypeScript frontend

- React components: PascalCase files (`TimelineView.tsx`).
- Hooks and utilities: kebab-case files; functions and variables use camelCase.
- Types/interfaces: PascalCase; true constants and environment variables use UPPER_SNAKE_CASE.
- Tests: `<source-name>.test.ts` or `<source-name>.test.tsx`.
- Use direct imports and the configured `src/` path alias; avoid barrel re-exports.

## Backend dependency policy

- `pyproject.toml` is the source of package metadata and tool configuration.
- `uv.lock` is committed. Production and development dependencies use exact locked resolutions; Docker is not required for ordinary local tests.
- Runtime foundation: Pydantic v2, AWS Lambda Powertools, `httpx`, and `boto3` (including `bedrock-runtime` Converse for candidate selection).
- Google Places and Routes use direct REST adapters rather than large generated clients so field masks, timeouts, and payload validation stay explicit.
- Standard-library `datetime` and `zoneinfo` drive timezone arithmetic; helpers must explicitly detect ambiguous and nonexistent local times.
- Do not add FastAPI or Mangum. Four HTTP routes do not justify a second web framework over Lambda Powertools routing.

## API contract policy

Pydantic models are authoritative for backend request and response validation. Public JSON uses camelCase aliases while Python code uses snake_case. Wave 1 exports a versioned JSON Schema artifact; frontend TypeScript contracts are generated or checked against that schema so the languages cannot drift silently.

The model-backed candidate selection boundary is a Python `Protocol`. Production wires one Bedrock Claude implementation. This is provider-isolated, not a promise of runtime multi-provider selection or automatic fallback.

## Testing policy

### What gets tested

| Layer | What | How |
|---|---|---|
| Solver | Every permutation rule, time-window feasibility, waits, ties, dropping | pytest unit tests + Hypothesis invariants |
| Time | IANA conversion, DST ambiguity/nonexistence, split and overnight intervals | pytest parameterization + Hypothesis boundaries |
| URL builder | Maps URL encoding, 2,048-character guard, overlapping parts | pytest unit tests |
| Pipeline adapters | Bedrock, Places, Routes, DynamoDB behavior | integration tests with mocked HTTP/AWS boundaries |
| API contract | Pydantic strictness, JSON Schema stability, camelCase response compatibility | contract tests |
| Frontend | Timeline, comparison, loading/error, sharing states | Vitest + React Testing Library |

### What does not get a committed suite

- Full browser end-to-end automation; component/integration tests plus agent-led Playwright MCP review cover the four-feature build.
- Visual regression.
- Live provider calls in ordinary test runs.

Infrastructure is validated with `sam validate`, `sam build`, and deployment smoke tests rather than mocked CloudFormation behavior.

### Running checks

```bash
# Backend
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
cd ..

# Infrastructure
sam validate --template-file infra/template.yaml
sam build --template-file infra/template.yaml

# Frontend
cd frontend
npm test
npm run lint
npm run typecheck
```

## Fixtures

Recorded provider responses remain in `docs/api-samples/` as the single canonical copies. Backend integration tests load them by repository-relative path and never duplicate them under `backend/`. They are real sanitized responses used through mocked boundaries, never production fallback data.

## Environment variables

`.env.example` documents placeholders only:

```text
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-6
BEDROCK_REGION=us-east-1
BEDROCK_MONTHLY_BUDGET_USD=5.00
BEDROCK_INPUT_USD_PER_MILLION_TOKENS=4.00
BEDROCK_OUTPUT_USD_PER_MILLION_TOKENS=20.00
GOOGLE_SERVER_KEY=replace-with-server-key
GOOGLE_MAPS_BROWSER_KEY=replace-with-referrer-restricted-browser-key
DYNAMODB_TABLE_CACHE=vialo-place-cache
DYNAMODB_TABLE_SHARES=vialo-shared-itineraries
DYNAMODB_TABLE_RATE_LIMITS=vialo-request-limits
RATE_LIMIT_HMAC_SECRET=replace-with-random-value
SHARE_SIGNING_SECRET=replace-with-random-value
SHARE_DELETION_SECRET=replace-with-random-value
POWERTOOLS_SERVICE_NAME=vialo-api
LOG_LEVEL=INFO
AWS_REGION=us-east-1
DYNAMODB_TABLE_BLOG=vialo-journal
MEDIA_BUCKET=vialo-journal-media
MEDIA_BASE_URL=/media
COGNITO_USER_POOL_ID=replace-after-deploy
COGNITO_CLIENT_ID=replace-after-deploy
COGNITO_REGION=us-east-1
VITE_COGNITO_DOMAIN=replace-after-deploy.auth.us-east-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=replace-after-deploy
```

The two `VITE_` values are build-time frontend configuration, not secrets: the Cognito app client has no secret and its redirect URI is pinned in the user pool. Journal variables load through `load_blog_config()`, which is deliberately separate from `load_config()` so that neither feature can break the other by being unconfigured. Added 2026-08-20 with the Journal.

`KIRO_API_KEY` is intentionally absent. It authenticates headless Kiro CLI automation and is not a documented model-provider credential for deployed application inference.
