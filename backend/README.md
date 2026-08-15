# Vialo backend

Python 3.12 Lambda implementation of Vialo's itinerary engine.

## Commands

```bash
uv sync --extra dev
uv run pytest --cov=vialo --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
./build-layer.sh
./verify-layer.sh
```

From the repository root, `make layer`, `make validate`, and `make build` use the locked layer build and pinned `aws-sam-cli==1.165.0` validation path.

## Runtime boundaries

- `src/vialo/domain/` is deterministic and provider/AWS independent.
- `services/anthropic_selector.py` is the production adapter behind `CandidateSelector`.
- Places and Routes use direct `httpx` REST clients with bounded retries and explicit field masks.
- DynamoDB repositories implement independently fresh place data, HMAC-keyed rate limits, and atomic explicit sharing.
- Public JSON is camelCase and schema version 1; Python remains snake_case.

The dependency layer is generated under `backend/layer/python/` and is ignored by Git. `verify-layer.sh` rejects source mixed into the layer, non-ARM64 native extensions, a non-CPython-3.12 ABI, and Lambda size-limit violations.
