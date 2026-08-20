#!/usr/bin/env bash
# Applies Vialo branding to the Cognito classic hosted sign-in page.
#
# Why this is a script and not a CloudFormation resource:
# AWS::Cognito::UserPoolUICustomizationAttachment can carry the CSS but has no
# way to attach the logo, because SetUICustomization takes the image as raw
# bytes. Splitting the two across CloudFormation and the CLI would mean a stack
# update could rewrite the CSS without the image and blank the logo. One call
# that sets both together is the only way to keep them consistent.
#
# Inputs are version-controlled: infra/cognito-hosted-ui.css and
# frontend/public/icon-192.png.
#
# Cognito validates the CSS against a fixed allowlist of classes and rejects the
# whole request if any class is unknown, so edits to the stylesheet must be
# re-applied with this script rather than assumed to work.
#
# Usage:
#   scripts/apply-cognito-branding.sh [user-pool-id] [client-id]
# Defaults are read from the deployed stack.
set -euo pipefail

STACK="${STACK_NAME:-vialo-backend-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CSS_FILE="$ROOT/infra/cognito-hosted-ui.css"
LOGO_FILE="$ROOT/frontend/public/icon-192.png"

[[ -f "$CSS_FILE" ]] || { echo "Missing $CSS_FILE" >&2; exit 1; }
[[ -f "$LOGO_FILE" ]] || { echo "Missing $LOGO_FILE" >&2; exit 1; }

# Cognito caps the hosted-UI logo at 100 KB.
size=$(wc -c < "$LOGO_FILE")
if [[ "$size" -gt 102400 ]]; then
  echo "Logo is ${size} bytes; Cognito's limit is 102400." >&2
  exit 1
fi

POOL_ID="${1:-}"
CLIENT_ID="${2:-}"

if [[ -z "$POOL_ID" ]]; then
  POOL_ID=$(aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='JournalUserPoolId'].OutputValue" --output text)
fi
if [[ -z "$CLIENT_ID" ]]; then
  CLIENT_ID=$(aws cloudformation describe-stacks --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='JournalUserPoolClientId'].OutputValue" --output text)
fi

[[ -n "$POOL_ID" && "$POOL_ID" != "None" ]] || { echo "Could not resolve the user pool id" >&2; exit 1; }
[[ -n "$CLIENT_ID" && "$CLIENT_ID" != "None" ]] || { echo "Could not resolve the client id" >&2; exit 1; }

echo "==> Applying hosted-UI branding to $POOL_ID / $CLIENT_ID"

version=$(aws cognito-idp set-ui-customization \
  --user-pool-id "$POOL_ID" \
  --client-id "$CLIENT_ID" \
  --css "$(cat "$CSS_FILE")" \
  --image-file "fileb://$LOGO_FILE" \
  --query 'UICustomization.CSSVersion' --output text)

echo "==> Applied. CSS version: $version"
echo "    Verify at the hosted UI sign-in page; the canvas should be cream (#fff8ea)"
echo "    and the submit button plum (#6f3e59), with the Vialo mark above the form."
