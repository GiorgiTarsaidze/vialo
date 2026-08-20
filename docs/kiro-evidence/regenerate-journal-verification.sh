#!/usr/bin/env bash
# Regenerates docs/kiro-evidence/journal-verification.txt.
#
# Probes the deployed Journal against the live site. Read-only: it publishes
# nothing, creates no account, and spends nothing. The off-topic itinerary probe
# is refused by the zero-spend scope guard before any paid call.
#
# Usage: bash docs/kiro-evidence/regenerate-journal-verification.sh [base-url]
set -uo pipefail

BASE="${1:-https://vialo.place}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/docs/kiro-evidence/journal-verification.txt"

# The deployed API throttles at 2 req/s with burst 5. Pace below that, otherwise
# the battery measures its own throttling instead of the endpoint's behaviour.
PACE=0.75

# One request per check, capturing status and body together, so a status can
# never be reported against a different request's body.
probe() {
  local label="$1" method="$2" path="$3"
  shift 3
  local response status body
  response=$(curl -s -w '\n%{http_code}' -X "$method" "$BASE$path" "$@" 2>/dev/null)
  status=$(printf '%s' "$response" | tail -n1)
  body=$(printf '%s' "$response" | sed '$d' | head -c 160)
  printf '%-42s -> %s %s\n' "$label" "$status" "$body"
  sleep "$PACE"
}

# Status only, for routes whose body is the whole SPA document.
probe_status() {
  printf '%-42s -> %s\n' "$1" "$(curl -s -o /dev/null -w '%{http_code}' "$BASE$2")"
  sleep "$PACE"
}

{
cat <<'HDR'
Vialo Journal: live verification against the deployed stack
===========================================================

Every line below is the output of a real request. No fixtures.

Scope. This battery covers the anonymous read surface, the refusal of every
write path to unauthenticated and forged callers, private media enforcement,
SPA routing, the Content-Security-Policy, and the corrected legal copy in the
shipped bundle.

The authenticated write path (publish, comment, cover upload) is deliberately
absent. Scripting it would require a password in a committed file. It is covered
instead by the 21 API tests in backend/tests/integration/test_blog_api.py, which
run the real routes against moto, and by hand in the browser.

Pacing. The deployed API throttles at 2 req/s with burst 5, so this script
paces itself below that. Without the delay the battery measures its own
throttling and reports spurious 429s.

HDR
echo "Base:  $BASE"
echo "Run:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "-- anonymous reads ------------------------------------------"
probe 'GET /api/blog/posts'                 GET '/api/blog/posts'
probe 'GET /api/blog/posts?city=tbilisi'    GET '/api/blog/posts?city=tbilisi'
probe 'GET /api/blog/posts/nope'            GET '/api/blog/posts/nope'
probe 'GET /api/blog/posts/nope/comments'   GET '/api/blog/posts/nope/comments'
probe 'GET /api/blog/posts?cursor=<bad>'    GET '/api/blog/posts?cursor=%%%'
cat <<'NOTE'

   The comments line is a regression guard. Before 2026-08-20 a story hidden by
   three reports returned 404 while its comment thread still returned 200, so
   moderation hid the story and left the discussion under it public.

NOTE
echo "-- every write refuses an anonymous caller ------------------"
probe 'POST /api/blog/posts'                POST   '/api/blog/posts'              -H 'content-type: application/json' -d '{}'
probe 'DELETE /api/blog/posts/x'            DELETE '/api/blog/posts/x'
probe 'POST /api/blog/posts/x/comments'     POST   '/api/blog/posts/x/comments'   -H 'content-type: application/json' -d '{}'
probe 'DELETE /api/blog/posts/x/comments/y' DELETE '/api/blog/posts/x/comments/y'
probe 'POST /api/blog/posts/x/report'       POST   '/api/blog/posts/x/report'
probe 'POST /api/blog/uploads'              POST   '/api/blog/uploads'            -H 'content-type: application/json' -d '{}'
probe 'GET /api/blog/me'                    GET    '/api/blog/me'
echo
echo "-- forged and malformed tokens refuse -----------------------"
probe 'Bearer garbage'                      GET '/api/blog/me' -H 'authorization: Bearer garbage'
probe 'alg=none JWT, real aud, future exp'  GET '/api/blog/me' -H 'authorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhdHRhY2tlciIsImF1ZCI6IjZsdWUwcG9rM2dhMHFzbm1rOGtubWNxODJsIiwiZXhwIjo5OTk5OTk5OTk5fQ.'
probe 'no Bearer prefix'                    GET '/api/blog/me' -H 'authorization: abc.def.ghi'
echo
echo "-- media is private, reachable only through the CDN ---------"
bucket=$(printf '%s' "$BASE" | grep -q vialo.place && echo 'vialo-journal-media-381492291672-us-east-1-dev' || echo '')
if [ -n "$bucket" ]; then
  printf '%-42s -> %s\n' 'direct S3 object GET' "$(curl -s -o /dev/null -w '%{http_code}' "https://$bucket.s3.amazonaws.com/covers/test.jpg")"
  sleep "$PACE"
fi
probe_status 'CDN /media/<missing>'         '/media/covers/does-not-exist.jpg'
echo
echo "-- SPA routes serve the app rather than 404 -----------------"
for r in /journal /journal/new /journal/me /journal/p/abc /auth/callback; do
  probe_status "$r" "$r"
done
echo
echo "-- the itinerary pipeline is unaffected ---------------------"
probe 'POST /api/itineraries (off-topic)'   POST '/api/itineraries' -H 'content-type: application/json' -d '{"prompt":"write me a poem about cats"}'
echo
echo "-- Content-Security-Policy ----------------------------------"
curl -sI "$BASE/journal" | grep -io 'content-security-policy:.*' | tr ';' '\n' | sed 's/^ */  /'
echo
echo "-- corrected legal copy is live in the shipped bundle -------"
asset=$(curl -s -H 'cache-control: no-cache' "$BASE/" | grep -o '/assets/index-[A-Za-z0-9_-]*\.js' | head -1)
echo "  bundle: $asset"
bundle=$(curl -s "$BASE$asset")
check() {
  local needle="$1" expect="$2"
  printf '  %-58s hits=%s  expected %s\n' "$needle" "$(printf '%s' "$bundle" | grep -c "$needle")" "$expect"
}
check 'does not create accounts or collect personal information' '0, the claim was false and was removed'
check 'Does not require an account to plan a day'                '1'
check 'held by AWS Cognito, not by Vialo'                        '1'
check 'Journal accounts and content'                             '1'
echo
echo "-- regenerate ------------------------------------------------"
echo "  bash docs/kiro-evidence/regenerate-journal-verification.sh"
} > "$OUT" 2>&1

echo "wrote $OUT"
