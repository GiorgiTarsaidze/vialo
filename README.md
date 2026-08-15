# Vialo

**Describe your day. Get one that actually fits.**

Vialo is a constraint solver for one day in a city. It grounds suggested stops to real Google Place IDs, interprets requested-date opening hours, computes a directed travel-time matrix, solves the retained route exactly, and returns a scheduled timeline with an honest naive-versus-optimized comparison. Google Maps is the final handoff, not the scheduling engine.

## Phase 3 backend

The backend is one Python 3.12 Lambda behind API Gateway HTTP API. It uses strict Pydantic contracts, Lambda Powertools, direct Google Places and Routes REST adapters, a provider-neutral candidate-selector boundary with Anthropic Claude in production, and three on-demand DynamoDB tables for place cache, rate limits, and explicit anonymous shares.

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

The committed test suite contains unit, property, integration, contract, infrastructure, and solver benchmark coverage. The final backend gate passed 225 tests with 85% coverage, strict mypy, Ruff, SAM validation/build, repository safety checks, and ARM64 layer verification. Ordinary tests mock provider and AWS boundaries and make no live provider calls.

## Configuration

Copy `.env.example` to a local ignored file and replace placeholders. Backend provider keys and HMAC secrets are server-side only. `KIRO_API_KEY` is intentionally not an application runtime credential.

The deployed development stack currently retains placeholder Anthropic, Places, and Routes values. Its zero-provider-spend validation paths are live, but provider-dependent itinerary generation must not be used until supported server-side credentials and a pinned Anthropic model ID are configured. The Google Maps browser key is separate: restrict it by production referrer and enable only the Maps JavaScript API. Never place Anthropic, Places, Routes, or HMAC secrets in frontend code.

## Deployment

The isolated development backend is deployed at:

```text
https://ap9i8up7k7.execute-api.us-east-1.amazonaws.com
```

Zero-provider-spend smoke tests verified invalid input, off-topic rejection, missing-share lookup, and deletion without a creator token. The successful ARM64 invocations also verify that the dependency layer imports in Lambda. Live candidate selection, Places grounding, route matrices, and paired geometry remain untested in this deployment until provider credentials are configured; no fixture or simulated itinerary is used as a fallback.

`infra/template.yaml` defines the `vialo-backend-dev` stack in `us-east-1`: ARM64 Lambda, HTTP API, explicit least-privilege IAM role, two seven-day log groups, and three PAY_PER_REQUEST DynamoDB tables with TTL and PITR disabled. There is no reserved or provisioned concurrency. All taggable resources carry `Project=vialo`, `vialo=true`, `Environment=dev`, and `ManagedBy=sam`. AWS Lambda layer-version resources do not support tags through CloudFormation or the Lambda tagging API, so the dependency layer is the documented non-taggable exception.

See `DEVLOG.md` and `.kiro/specs/itinerary-engine/` for decisions, invariants, and acceptance criteria.

## License

[MIT](LICENSE)
