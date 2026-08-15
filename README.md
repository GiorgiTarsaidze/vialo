# Vialo

**Describe your day. Get one that actually fits.**

Vialo is a constraint solver for one day in a city. It grounds suggested stops to real Google Place IDs, interprets requested-date opening hours, computes a directed travel-time matrix, solves the retained route exactly, and returns a scheduled timeline with an honest naive-versus-optimized comparison. Google Maps is the final handoff, not the scheduling engine.

## Backend

The backend is one Python 3.12 Lambda behind API Gateway HTTP API. It uses strict Pydantic contracts, Lambda Powertools, direct Google Places and Routes REST adapters (unified `GOOGLE_SERVER_KEY`), a provider-neutral candidate-selector boundary with AWS Bedrock Claude Sonnet 4.6 in production, and three on-demand DynamoDB tables for place cache, rate limits (including Bedrock spend tracking), and explicit anonymous shares.

Bedrock inference is budget-capped: a fail-closed DynamoDB-backed spend limiter reserves conservative maximum micro-USD amounts before each call and refunds unused reservations after confirmed usage. The monthly cap defaults to $5 and is configurable via `BEDROCK_MONTHLY_BUDGET_USD`. This is Vialo application-level metering—conservative by design (uses worst-case max_output_tokens pricing at $4/M input, $20/M output), synchronous, and fail-closed. It is distinct from AWS Budgets, which evaluates delayed billing data and cannot prevent a single request from overshooting. Botocore retries are disabled (`total_max_attempts: 1`) so one reservation maps to exactly one wire call; missing or malformed usage retains the full reservation.

Third-party packages are built separately into an ARM64 Lambda layer; function source contains only `vialo` application code. No fixture or hard-coded itinerary is used as production fallback behavior.

## Local validation

Prerequisites: Python 3.12, `uv`, Docker for local tooling where supported, AWS CLI, and network access for the pinned SAM CLI tool.

```bash
uv sync --project backend --extra dev
make test
make lint
make typecheck
make layer
make validate
make build
```

The committed test suite contains unit, property, integration, contract, infrastructure, and solver benchmark coverage. Ordinary tests mock provider and AWS boundaries and make no live provider calls.

## Configuration

Copy `.env.example` to a local ignored file and replace placeholders. Google and HMAC secrets are server-side only. Bedrock access uses the Lambda execution IAM role (no API key or secret); IAM permissions are scoped to `bedrock:InvokeModel` on the specific inference-profile ARN and the three backing foundation-model ARNs (us-east-1, us-east-2, us-west-2).

The Google Maps browser key is separate: restrict it by production referrer and enable only the Maps JavaScript API. Never place Bedrock credentials, Google server keys, or HMAC secrets in frontend code.

## Deployment

`infra/template.yaml` defines the deployed `vialo-backend-dev` stack in `us-east-1`: ARM64 Lambda, HTTP API with default throttling (2 req/s, burst 5), explicit least-privilege IAM role (Bedrock + DynamoDB + CloudWatch), two seven-day log groups, three PAY_PER_REQUEST DynamoDB tables with TTL, and a TLS 1.2 REGIONAL custom domain (`api.vialo.place`). There is no reserved or provisioned concurrency. All taggable resources carry `Project=vialo`, `vialo=true`, `Environment=dev`, and `ManagedBy=sam`. Layer-version tagging is unsupported through CloudFormation or the Lambda tagging API.

The active execute-api endpoint is `https://ap9i8up7k7.execute-api.us-east-1.amazonaws.com`. The AWS custom domain and `$default` mapping are provisioned, but `https://api.vialo.place` remains pending the DNS-only Cloudflare CNAME `api` → `d-qlg5m9tufa.execute-api.us-east-1.amazonaws.com`.

Live production validation confirmed Bedrock Sonnet 4.6 candidate selection, Google Places grounding/opening intervals, directed Routes data, exact scheduling, paired real route polylines, and Maps handoff URLs in one schema-version-1 response. The public endpoint also returned `429 RATE_LIMITED` after five accepted requests from one IP. Application Bedrock accounting settled confirmed token usage while remaining below the $5 monthly hard cap; no raw prompt field was returned.

See `DEVLOG.md` and `.kiro/specs/itinerary-engine/` for decisions, invariants, and acceptance criteria.

## License

[MIT](LICENSE)
