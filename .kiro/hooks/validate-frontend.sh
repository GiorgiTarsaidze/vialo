#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || exit 0
cd "$root"

if [[ ! -f frontend/package.json ]]; then
  printf '%s\n' 'frontend validation skipped: frontend/package.json does not exist yet'
  exit 0
fi

npm --prefix frontend run lint --if-present
npm --prefix frontend run typecheck --if-present
printf '%s\n' 'frontend validation passed'
