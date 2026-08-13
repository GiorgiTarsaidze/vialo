---
inclusion: always
---

# Structure — Vialo

## Repository layout

```
vialo/
├── .kiro/
│   ├── steering/           # product.md, tech.md, structure.md, design-system.md
│   ├── specs/              # feature specs (requirements.md, design.md, tasks.md)
│   └── hooks/              # event-driven automation
├── frontend/
│   ├── public/
│   │   ├── index.html
│   │   └── favicon.svg
│   ├── src/
│   │   ├── components/     # React components, one per file
│   │   ├── hooks/          # custom React hooks
│   │   ├── lib/            # utilities, API client, types
│   │   ├── styles/         # global CSS, design tokens
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── tests/              # frontend tests (colocated alternative: *.test.tsx next to source)
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── backend/
│   ├── src/
│   │   ├── handler.ts      # Lambda entry point
│   │   ├── pipeline/       # one file per pipeline step
│   │   │   ├── select-stops.ts
│   │   │   ├── ground-places.ts
│   │   │   ├── compute-matrix.ts
│   │   │   ├── solve-route.ts
│   │   │   └── build-maps-url.ts
│   │   ├── services/       # external API wrappers (Places, Routes, Claude, DynamoDB)
│   │   ├── models/         # TypeScript types and Zod schemas
│   │   └── utils/          # shared helpers (rate-limit, validation, sanitization)
│   ├── tests/
│   │   ├── unit/           # pure logic tests (solver, URL builder, validation)
│   │   └── integration/    # tests against API fixtures
│   ├── fixtures/           # recorded API responses from Phase 1 validation
│   ├── package.json
│   └── tsconfig.json
├── infra/                  # IaC (CDK or SAM template)
├── docs/
│   ├── api-samples/        # raw API responses from validation gate
│   └── kiro-evidence/      # screenshots and recordings (large files gitignored)
├── DEVLOG.md
├── KIRO.md
├── README.md
├── LICENSE
├── .env.example            # documents required env vars, no real values
├── .gitignore
└── package.json            # root workspace (if using npm workspaces)
```

## Naming conventions

- **Files:** kebab-case for all source files (`solve-route.ts`, `timeline-view.tsx`)
- **Components:** PascalCase for React component files (`TimelineView.tsx`) — exception to kebab-case rule for React convention
- **Directories:** kebab-case (`compute-matrix/`, `design-system/`)
- **Types/Interfaces:** PascalCase (`ItineraryStop`, `RouteMatrix`)
- **Functions:** camelCase (`solveRoute`, `buildMapsUrl`)
- **Constants:** UPPER_SNAKE_CASE for environment variables and true constants (`MAX_STOPS`, `CACHE_TTL_MS`)
- **Test files:** `<source-name>.test.ts` or `<source-name>.test.tsx`

## Testing policy

### What gets tested

| Layer | What | How |
|-------|------|-----|
| Solver | All permutation logic, time-window validation, infeasibility detection | Unit tests with synthetic data |
| URL builder | Correct Maps URL construction, 2048-char guard, edge cases | Unit tests |
| Pipeline steps | Each step in isolation with recorded API fixtures | Integration tests with mocked HTTP |
| Input validation | Prompt length, rate limit, scope check | Unit tests |
| Frontend components | Timeline rendering, comparison view, loading/error states | Component tests (React Testing Library) |

### What does NOT get tested (time constraint)

- End-to-end browser automation (Cypress/Playwright) — manual testing suffices for 4 features
- Infrastructure (CDK/SAM correctness verified by deployment)
- Visual regression

### Test runner

- **Backend:** Vitest (fast, TypeScript-native, compatible with Jest API)
- **Frontend:** Vitest + React Testing Library

### Running tests

```bash
# Backend
cd backend && npm test

# Frontend
cd frontend && npm test

# All (from root, if workspaces configured)
npm test
```

### Fixtures

Recorded API responses from the Phase 1 validation gate live in `backend/fixtures/`. Tests use these as mock responses to verify pipeline logic without real API calls. This ensures nothing is simulated — the fixtures are real responses, and the logic is tested against them.

## Import conventions

- Absolute imports from `src/` root using TypeScript path aliases (`@/components/...`, `@/lib/...`)
- No barrel files (`index.ts` re-exports) — direct imports only for clarity and tree-shaking
- External imports first, then internal, separated by a blank line

## Environment variables

All secrets and configuration live in `.env` (gitignored). `.env.example` documents every required variable with placeholder values:

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_PLACES_KEY=AIza...
GOOGLE_ROUTES_KEY=AIza...
GOOGLE_MAPS_BROWSER_KEY=AIza...
DYNAMODB_TABLE_CACHE=vialo-place-cache
DYNAMODB_TABLE_SHARES=vialo-shared-itineraries
AWS_REGION=us-east-1
```
