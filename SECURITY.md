# Security policy

## Supported versions

Security fixes target the latest released minor version.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a public issue with
vault excerpts, filesystem paths, database copies, credentials, or personal data. Include the
affected version, impact, minimal synthetic reproduction, and suggested mitigation when known.

## Trust boundary

Quick Vault Retriever reads a caller-selected SQLite projection. It must not mutate the projection,
canonical JSONL records, or source vault. The initial release makes no network requests and invokes
no AI model. Treat Raycast output, terminal scrollback, clipboard contents, and downstream tools as
separate disclosure surfaces.
