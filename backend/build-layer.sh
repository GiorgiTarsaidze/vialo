#!/usr/bin/env bash
# Build the Lambda dependency layer for ARM64 Python 3.12
# Uses uv for deterministic dependency resolution — never bare pip.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAYER_DIR="${SCRIPT_DIR}/layer"
PYTHON_VERSION="3.12"
PLATFORM="manylinux2014_aarch64"

echo "==> Cleaning previous layer..."
rm -rf "${LAYER_DIR}/python" "${LAYER_DIR}/requirements.txt"

echo "==> Exporting production dependencies from uv.lock..."
cd "${SCRIPT_DIR}"
uv export --quiet --no-dev --no-editable --no-emit-project --locked -o "${LAYER_DIR}/requirements.txt"

echo "==> Installing dependencies for Lambda (arm64, python ${PYTHON_VERSION})..."
uv pip install \
    --python "${PYTHON_VERSION}" \
    -r "${LAYER_DIR}/requirements.txt" \
    --target "${LAYER_DIR}/python" \
    --python-platform "${PLATFORM}" \
    --only-binary=:all: \
    --quiet

echo "==> Layer built successfully at ${LAYER_DIR}/python/"
echo "    Size: $(du -sh "${LAYER_DIR}/python" | cut -f1)"
echo "    Platform: ${PLATFORM}"
echo "    Python: ${PYTHON_VERSION}"
