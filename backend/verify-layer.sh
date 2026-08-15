#!/usr/bin/env bash
# Verify the dependency-only ARM64 Python 3.12 Lambda layer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAYER_DIR="${SCRIPT_DIR}/layer"
PYTHON_DIR="${LAYER_DIR}/python"

for package in pydantic aws_lambda_powertools httpx boto3; do
    test -d "${PYTHON_DIR}/${package}"
done
test ! -e "${PYTHON_DIR}/vialo"
test -f "${LAYER_DIR}/requirements.txt"
! grep -Eq '(^|[[:space:]])vialo(@|==|[[:space:]])' "${LAYER_DIR}/requirements.txt"
grep -q -- '--hash=sha256:' "${LAYER_DIR}/requirements.txt"

# Assert no anthropic package is present (we use boto3 bedrock-runtime directly)
test ! -d "${PYTHON_DIR}/anthropic"
! grep -iq 'anthropic' "${LAYER_DIR}/requirements.txt"

native_count=0
while IFS= read -r -d '' extension; do
    native_count=$((native_count + 1))
    description="$(file "${extension}")"
    printf '%s\n' "${description}"
    printf '%s' "${description}" | grep -Eq 'ARM aarch64|ARM64'
    basename "${extension}" | grep -q 'cpython-312'
done < <(find "${PYTHON_DIR}" -type f -name '*.so' -print0)
test "${native_count}" -gt 0

read -r uncompressed_bytes zipped_bytes < <(
    python3 - "${LAYER_DIR}" <<'PY'
from pathlib import Path
import sys
import tempfile
import zipfile

root = Path(sys.argv[1])
uncompressed = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
with tempfile.NamedTemporaryFile(suffix=".zip") as archive:
    with zipfile.ZipFile(archive.name, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(root))
    zipped = Path(archive.name).stat().st_size
print(uncompressed, zipped)
PY
)

test "${uncompressed_bytes}" -lt 262144000
test "${zipped_bytes}" -lt 52428800
printf 'layer_verification=PASS native_extensions=%s uncompressed_bytes=%s zipped_bytes=%s\n' \
    "${native_count}" "${uncompressed_bytes}" "${zipped_bytes}"
