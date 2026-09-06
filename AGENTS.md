# Agent instructions

Repository files and repo-local `.go/` state are authoritative. Private vault content is never a
fallback source for repository work.

## Start work

1. Read `.go/project.json`, `.go/vision.json`, `.go/hierarchy.json`, and the applicable task.
2. Run `./go doctor . --platform auto --agent auto --json` and require an exact compatible stack.
3. Run `./go validate .` and `./go status . --json`.
4. Claim exactly one ready task before editing.
5. Stay within the task's declared scope and preserve unrelated changes.

## Product boundaries

- Open vault projections with SQLite URI `mode=ro&immutable=1` and `PRAGMA query_only = ON`.
- Never add a canonical JSONL writer, mutation route, background indexer, or agent shell.
- Keep retrieval general; entity questions are examples, not the organizing abstraction.
- Return stable record citations and abstain when evidence is absent, stale, or malformed.
- Keep default output bounded and avoid raw paths or full private records.
- Use only synthetic data in tests, documentation, screenshots, and examples.
- Never commit a vault database, query history, local runtime path, secret, generated report, or
  private benchmark fixture.
- Do not add GitHub Actions. `make check` is the canonical local gate.

## Engineering

- Python 3.11+, `uv`, `ruff`, `ty`, and pytest.
- Use TDD for observable behavior changes: one RED test, minimal GREEN implementation, refactor.
- Keep the CLI contract versioned and the Raycast adapter thin.
- Use `apply_patch` for hand-authored edits and non-interactive Git commands.

## Finish

Run `make check`, record architecture conformance when required, finish the claimed `.go` task with
attributed evidence, and commit one completed task at a time. Do not claim success from intent or a
narrow check.
