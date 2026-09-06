#!/bin/bash

# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Query JSONL Vault
# @raycast.mode fullOutput
# @raycast.packageName Quick Vault Retriever
# @raycast.argument1 {"type":"text","placeholder":"Ask your vault"}

# Optional parameters:
# @raycast.icon 🔎

# Documentation:
# @raycast.description Retrieve fast, bounded, source-cited evidence from a local JSONL Vault
# @raycast.author Viggo Meesters
# @raycast.authorURL https://github.com/viggomeesters

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
QUERY="${1:-}"

if [ -n "${QUICK_VAULT_BIN:-}" ]; then
  COMMAND=("$QUICK_VAULT_BIN")
elif command -v quick-vault >/dev/null 2>&1; then
  COMMAND=("$(command -v quick-vault)")
else
  UV_BIN=""
  for candidate in "$(command -v uv 2>/dev/null || true)" /opt/homebrew/bin/uv /usr/local/bin/uv; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
      UV_BIN="$candidate"
      break
    fi
  done
  if [ -z "$UV_BIN" ]; then
    echo "Quick Vault Retriever is not installed and uv is unavailable."
    exit 3
  fi
  COMMAND=("$UV_BIN" run --quiet --project "$REPO_ROOT" quick-vault)
fi

set +e
OUTPUT="$("${COMMAND[@]}" query "$QUERY" --format markdown 2>&1)"
STATUS=$?
set -e
printf '%s\n' "$OUTPUT"

case "$STATUS" in
  0|4|6) exit 0 ;;
  *) exit "$STATUS" ;;
esac
