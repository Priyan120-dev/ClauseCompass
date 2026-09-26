#!/usr/bin/env bash
# Check that repository size is strictly under 10 MB (excluding .git and .venv)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Checking ClauseCompass repository size..."
cd "${REPO_ROOT}"

# Calculate size in bytes excluding .git and .venv
if command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null; then
    TOTAL_BYTES=$(git ls-files | tr '\n' '\0' | wc -c --files0-from=- | tail -n 1 | awk '{print $1}')
else
    # Fallback to find
    TOTAL_BYTES=$(find . -not -path '*/.*' -not -path './.venv*' -not -path './venv*' -type f -exec du -b {} + | awk '{s+=$1} END {print s}')
fi

MAX_BYTES=$((10 * 1024 * 1024))
TOTAL_KB=$((TOTAL_BYTES / 1024))
TOTAL_MB=$(awk "BEGIN {printf \"%.2f\", ${TOTAL_BYTES} / (1024 * 1024)}")

echo "Total tracked repository size: ${TOTAL_MB} MB (${TOTAL_KB} KB, ${TOTAL_BYTES} bytes)"

if [ "${TOTAL_BYTES}" -gt "${MAX_BYTES}" ]; then
    echo "ERROR: Repository size exceeds 10 MB limit!"
    exit 1
else
    echo "SUCCESS: Repository size is within 10 MB limit."
    exit 0
fi
