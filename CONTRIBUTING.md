# Contributing

Thank you for improving Quick Vault Retriever.

## Setup

```bash
git clone https://github.com/viggomeesters/quick-vault-retriever.git
cd quick-vault-retriever
uv sync --all-groups
make check
```

## Workflow

1. Read `AGENTS.md`, `docs/vision.json`, and `docs/architecture.md`.
2. Inspect repo-local work with `./go status . --json`.
3. Add one public-behavior test and observe the expected RED failure.
4. Implement the smallest GREEN change and refactor while green.
5. Run `make check` before submitting a focused pull request.

Public contributions must use synthetic fixtures. Never attach or commit a real vault database,
record body, query log, private path, screenshot, or benchmark corpus.
