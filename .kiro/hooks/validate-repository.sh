#!/usr/bin/env bash
set -euo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$root" ]] || exit 0
cd "$root"

git diff --check

if git ls-files | grep -q '^\.tmp/'; then
  printf '%s\n' 'repository validation failed: ignored private workspace content is tracked' >&2
  exit 1
fi

secret_pattern='AIza[0-9A-Za-z_-]{30,}|sk-ant-[0-9A-Za-z_-]{20,}|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|gh[pousr]_[0-9A-Za-z]{30,}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'

if git grep -q -I -E "$secret_pattern" -- .; then
  printf '%s\n' 'repository validation failed: a tracked file matches a credential pattern' >&2
  exit 1
fi

if git grep -q -I -E --untracked --exclude-standard "$secret_pattern" -- .; then
  printf '%s\n' 'repository validation failed: a public untracked file matches a credential pattern' >&2
  exit 1
fi

printf '%s\n' 'repository validation passed'
