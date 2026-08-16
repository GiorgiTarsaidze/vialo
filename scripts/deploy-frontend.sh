#!/usr/bin/env bash
set -euo pipefail

# Vialo frontend deployment script
# Builds the frontend with VITE_GOOGLE_MAPS_BROWSER_KEY, syncs to S3,
# and invalidates CloudFront.
#
# Required environment variables:
#   VITE_GOOGLE_MAPS_BROWSER_KEY — referrer-restricted Maps JS API key (build time only)
#   FRONTEND_BUCKET_NAME         — S3 bucket name (e.g. vialo-frontend-123456789012-us-east-1-dev)
#   FRONTEND_DISTRIBUTION_ID     — CloudFront distribution ID
#
# Usage:
#   VITE_GOOGLE_MAPS_BROWSER_KEY=AIza... \
#   FRONTEND_BUCKET_NAME=vialo-frontend-dev \
#   FRONTEND_DISTRIBUTION_ID=E1234ABCDEF \
#   ./scripts/deploy-frontend.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
DIST_DIR="$FRONTEND_DIR/dist"

# --- Validate required environment variables ---
: "${VITE_GOOGLE_MAPS_BROWSER_KEY:?Error: VITE_GOOGLE_MAPS_BROWSER_KEY is required}"
: "${FRONTEND_BUCKET_NAME:?Error: FRONTEND_BUCKET_NAME is required}"
: "${FRONTEND_DISTRIBUTION_ID:?Error: FRONTEND_DISTRIBUTION_ID is required}"

echo "==> Building frontend..."
cd "$FRONTEND_DIR"
npm ci --silent
VITE_GOOGLE_MAPS_BROWSER_KEY="$VITE_GOOGLE_MAPS_BROWSER_KEY" npm run build

if [ ! -d "$DIST_DIR" ]; then
  echo "Error: Build output not found at $DIST_DIR"
  exit 1
fi

echo "==> Syncing hashed assets (immutable cache)..."
# Sync all files with content-hash in name with immutable caching
aws s3 sync "$DIST_DIR/assets/" "s3://$FRONTEND_BUCKET_NAME/assets/" \
  --cache-control "public, max-age=31536000, immutable" \
  --delete

echo "==> Syncing root files (no-cache for index.html)..."
# Sync index.html with no-cache so CloudFront always revalidates
aws s3 cp "$DIST_DIR/index.html" "s3://$FRONTEND_BUCKET_NAME/index.html" \
  --cache-control "no-cache, no-store, must-revalidate"

# Sync remaining root-level files (favicon, robots.txt, etc.) with short cache
aws s3 sync "$DIST_DIR/" "s3://$FRONTEND_BUCKET_NAME/" \
  --exclude "assets/*" \
  --exclude "index.html" \
  --cache-control "public, max-age=3600" \
  --delete

echo "==> Invalidating CloudFront distribution..."
INVALIDATION_ID=$(aws cloudfront create-invalidation \
  --distribution-id "$FRONTEND_DISTRIBUTION_ID" \
  --paths "/index.html" "/" \
  --query 'Invalidation.Id' \
  --output text)

echo "==> Invalidation created: $INVALIDATION_ID"
echo "==> Frontend deployment complete."
echo "    Bucket:       s3://$FRONTEND_BUCKET_NAME"
echo "    Distribution: $FRONTEND_DISTRIBUTION_ID"
echo "    URL:          https://vialo.place"
