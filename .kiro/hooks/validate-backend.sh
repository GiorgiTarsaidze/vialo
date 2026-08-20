#!/usr/bin/env bash
# Backend validation hook: Ruff lint, Ruff format, strict mypy, and pytest.
#
# Wired as a Kiro `stop` hook in .kiro/agents/backend-engineer.json so a turn
# that touched backend code cannot end while the release gate is red.
# Exits 0 with a skip message when the backend package is not present yet.
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || exit 0
cd "$root"

if [[ ! -f backend/pyproject.toml ]]; then
  printf '%s\n' 'backend validation skipped: backend/pyproject.toml does not exist yet'
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '%s\n' 'backend validation skipped: uv is not installed' >&2
  exit 0
fi

cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
printf '%s\n' 'backend validation passed'
