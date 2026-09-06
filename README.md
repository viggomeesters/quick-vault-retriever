# Quick Vault Retriever

Quick Vault Retriever is a local-first command-line tool for querying a JSONL Vault SQLite
projection from Raycast or a terminal. It returns small, source-cited evidence packets instead of
letting an agent roam through private files.

## Why it exists

Opening a chat agent is excessive when the question is simple and the evidence is already local.
Quick Vault Retriever makes broad vault search feel like a calculator: invoke it, inspect the best
evidence, and continue. It is not limited to contacts or entity questions; it searches the complete
FTS projection using ordinary natural-language terms.

## Product contract

- Read-only: SQLite is opened in immutable, query-only mode.
- Freshness-aware: incompatible or stale projections fail closed when a ledger watermark is given.
- Bounded: output limits hits and snippet length.
- Cited: every hit carries its stable JSONL record identifier.
- Honest: no matching evidence produces an explicit `not_found` result.
- Local by default: version 0.1 performs no model or network call.

## Installation

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), SQLite with FTS5, and optionally
Raycast on macOS.

```bash
git clone https://github.com/viggomeesters/quick-vault-retriever.git
cd quick-vault-retriever
uv sync --all-groups
uv run quick-vault --help
```

## Usage

```bash
uv run quick-vault query "What did we decide about the migration?" \
  --runtime /path/to/jsonl-vault/default
```

Machine-readable output:

```bash
uv run quick-vault query "project context" --runtime /path/to/default --format json
```

The Raycast adapter and its installation steps are documented in
[`docs/raycast.md`](docs/raycast.md).

## Architecture

```text
Raycast or shell
      |
      v
Quick Vault CLI ---- freshness gate
      |
      v
SQLite FTS5 (immutable, query-only)
      |
      v
bounded evidence packet + jsonl://record/<id>
```

The SQLite projection is derived state. Canonical JSONL ownership and all mutations remain outside
this project. See [`docs/architecture.md`](docs/architecture.md) and
[`docs/vision.json`](docs/vision.json).

## Development

```bash
uv sync --all-groups
make check
```

The local gate validates formatting, lint, types, tests, coverage, design contracts, shell syntax,
repository privacy, and repo-local Go workflow state. This project intentionally does not use
GitHub Actions; validation is deterministic and repository-local.

Start with [`docs/onboarding.md`](docs/onboarding.md). Repository work is tracked in `.go/`; run
`./go status . --json` to inspect the next claimable task.

## Privacy and security

Do not commit vault databases, records, query logs, private fixtures, generated reports, or local
runtime configuration. The CLI does not send queries or evidence over the network. Report security
issues using [`SECURITY.md`](SECURITY.md).

## Release

Releases use semantic versioning. Maintainers run `make check`, inspect the privacy audit, tag the
validated commit, and publish release notes derived from [`CHANGELOG.md`](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 Viggo Meesters.
