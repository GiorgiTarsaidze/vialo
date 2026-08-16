# Vialo

**Describe your day. Get one that actually fits.**

Vialo is a constraint solver for one day in a city. It grounds suggested stops to real Google Place IDs, interprets requested-date opening hours, computes a directed travel-time matrix, solves the retained route exactly, and returns a scheduled timeline with an honest naive-versus-optimized comparison. Google Maps is the final handoff, not the scheduling engine.

## Frontend

The frontend is a mobile-first React 18 + TypeScript SPA built with Vite. It provides the natural-language input, factual pipeline loading state, honest route comparison, one Google Maps overlay, complete arrival/travel/wait/departure timeline, dropped-stop diagnostics, Maps handoff, and explicit anonymous sharing. Shared permalinks are read-only; only the creating browser receives a separate deletion capability stored in local storage.

The browser calls only same-origin `/api/*` routes through CloudFront. It validates the typed response at runtime, and a committed JSON Schema plus backend drift test keeps the TypeScript contract synchronized with the authoritative Pydantic model. No production fixture or hard-coded itinerary fallback exists.

## Backend

The backend is one Python 3.12 Lambda behind API Gateway HTTP API. It uses strict Pydantic contracts, Lambda Powertools, direct Google Places and Routes REST adapters (unified `GOOGLE_SERVER_KEY`), a provider-neutral candidate-selector boundary with AWS Bedrock Claude Sonnet 4.6 in production, and three on-demand DynamoDB tables for place cache, rate limits (including Bedrock spend tracking), and explicit anonymous shares.

Bedrock inference is budget-capped: a fail-closed DynamoDB-backed spend limiter reserves conservative maximum micro-USD amounts before each call and refunds unused reservations after confirmed usage. The monthly cap defaults to $5 and is configurable via `BEDROCK_MONTHLY_BUDGET_USD`. This is Vialo application-level metering—conservative by design (uses worst-case max_output_tokens pricing at $4/M input, $20/M output), synchronous, and fail-closed. It is distinct from AWS Budgets, which evaluates delayed billing data and cannot prevent a single request from overshooting. Botocore retries are disabled (`total_max_attempts: 1`) so one reservation maps to exactly one wire call; missing or malformed usage retains the full reservation.

Third-party packages are built separately into an ARM64 Lambda layer; function source contains only `vialo` application code.

## Local validation

Prerequisites: Python 3.12, `uv`, Node.js/npm, AWS CLI, and network access for the pinned SAM CLI tool.

```bash
# Backend and infrastructure
uv sync --project backend --extra dev
make test
make lint
make typecheck
make layer
make validate
make build

# Frontend
cd frontend
npm ci
npm run generate:contracts
npm run lint
npm run typecheck
npm test
VITE_GOOGLE_MAPS_BROWSER_KEY=replace-with-referrer-restricted-key npm run build
```

The release gate currently passes 396 backend tests and 93 frontend tests, strict mypy and TypeScript checks, Ruff and ESLint, source and transformed SAM validation, an ARM64 layer check, a production Vite build, and `npm audit` with zero known vulnerabilities. Ordinary tests mock provider and AWS boundaries and make no live provider calls.

## Configuration

Copy `.env.example` to a local ignored file and replace placeholders. Google and HMAC secrets are server-side only. Bedrock access uses the Lambda execution IAM role (no API key or secret); IAM permissions are scoped to `bedrock:InvokeModel` on the specific inference-profile ARN and the three backing foundation-model ARNs (us-east-1, us-east-2, us-west-2).

The Google Maps browser key is separate and visible in the browser bundle by design. Restrict it to `https://vialo.place/*` (plus explicitly approved local origins) and enable only the Maps JavaScript API. Never place Bedrock credentials, Google server keys, or HMAC secrets in frontend code.

## Deployment

`infra/template.yaml` defines the deployed `vialo-backend-dev` stack in `us-east-1`: ARM64 Lambda, HTTP API with default throttling (2 req/s, burst 5), explicit least-privilege IAM, two seven-day log groups, three PAY_PER_REQUEST DynamoDB tables with TTL, a TLS 1.2 REGIONAL API domain, a private encrypted S3 frontend bucket, and CloudFront with Origin Access Control. CloudFront owns frontend TLS, applies CSP and security headers, rewrites extensionless SPA routes without masking `/api/*` or asset failures, and proxies uncached same-origin API requests.

The API endpoints are `https://ap9i8up7k7.execute-api.us-east-1.amazonaws.com` and `https://api.vialo.place`. Live verification confirmed DNS, hostname-matched ACM coverage, TLS, and the `$default` API mapping.

The frontend distribution is deployed at `https://d1topuming9zvf.cloudfront.net`. Live smoke and Playwright review confirmed the 360/390/1440 layouts, loading and typed error states, a real computed itinerary, timeline and comparison data, Maps handoff, same-origin API routing, anonymous share create/read/delete, keyboard navigation, reduced motion, security headers, and private S3 enforcement. The referrer-restricted Maps key intentionally rejects this temporary CloudFront hostname.

The production site is live at `https://vialo.place`, with `/api/*` proxied same-origin through CloudFront and `https://api.vialo.place` available as the direct API hostname. Live Playwright verification confirmed the branded responsive experience, progressive pipeline state, Maps presentation, typed errors, and a real itinerary from the exact reported Tbilisi prompt. That run resolved the intended Tbilisi Sports Palace at May Square, rolled the date-less elapsed 09:00 window to the next local day, scheduled verified stops with ratings and attributed photos, and displayed real naive-versus-optimized route evidence.

## Fonts

The frontend self-hosts the Latin subsets of **Inter** and **Newsreader**, both licensed under the SIL Open Font License 1.1. The pinned Fontsource packages include the license metadata; production makes no third-party font request.

See `DEVLOG.md`, `frontend/README.md`, and `.kiro/specs/itinerary-engine/` for decisions, invariants, and acceptance criteria.

## License

[MIT](LICENSE)
