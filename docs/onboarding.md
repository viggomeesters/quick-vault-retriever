# Onboarding

Quick Vault Retriever has one primary flow: a query enters through the CLI, is matched against a
read-only FTS5 projection, and leaves as bounded cited evidence.

## Builder route

1. Start at `src/quick_vault_retriever/cli.py`; the intentionally small module owns the public
   command, retrieval, result contract, and renderer.
2. Read `tests/test_cli.py` for the subprocess contract and `tests/test_retriever.py` for ranking,
   freshness, privacy, and failure states.
3. Read `tests/test_raycast.py` for the launcher boundary.
4. Run `make check` after changes.

## Reviewer route

Review trust boundaries first: database URI flags, `PRAGMA query_only`, schema/freshness checks,
bounded output, stable exit codes, and absence of filesystem paths in results. Then inspect ranking
and missing-evidence tests.

## Product route

Read `docs/vision.json` for the product promise, non-goals, acceptance scorecard, and public-safety
contract. Read `.go/vision.json` and `./go status . --json` for durable direction and work state.

## Power-user route

Install with `uv sync`, call `quick-vault query`, and add the script under `raycast/` to Raycast.
Use JSON output for a trusted local downstream formatter. Do not expose that output to a model or
network service without making a separate privacy decision.
