#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

uv run ruff format --check .
uv run ruff check .
if [ -d src ]; then uv run ty check src; fi
if [ -d tests ]; then uv run pytest; fi
uv run python scripts/validate_design.py
bash -n go scripts/*.sh
./go validate .

tracked="$(git ls-files 2>/dev/null || true)"
if printf '%s\n' "$tracked" | grep -E '(^|/)(\.env($|\.)|id_(rsa|dsa|ecdsa|ed25519)(\.|$)|.*\.(pem|key|p12|sqlite|sqlite3|db)$|private-fixtures/|runtime/|benchmark-results/)' >/dev/null; then
  echo "privacy gate: forbidden tracked filename" >&2
  exit 1
fi
if git grep -IEn '(BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})' -- ':!uv.lock' >/dev/null 2>&1; then
  echo "privacy gate: credential-like content detected" >&2
  exit 1
fi
echo "privacy gate: passed"
