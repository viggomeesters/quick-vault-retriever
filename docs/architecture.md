# Architecture

## System boundary

Quick Vault Retriever is a read model over an existing JSONL Vault SQLite projection. It neither
owns canonical knowledge nor produces the index.

```text
[Raycast Script Command]       [Terminal]
           \                      /
            \                    /
             v                  v
               [quick-vault CLI]
                  |     |     |
          validate   query   render
                  |     |     |
                  v     v     v
            [SQLite FTS5 projection]
               mode=ro + immutable
                       |
                       v
             [bounded evidence packet]
```

## Components

- **CLI:** validates arguments, resolves the configured runtime, chooses JSON or Markdown output,
  and maps result states to stable exit codes.
- **Retriever:** tokenizes broad natural-language input, queries FTS5, ranks term coverage, and
  returns bounded snippets. It does not assume the query targets a person or entity.
- **Freshness gate:** verifies the projection schema and optionally compares its ledger sequence to
  a caller-supplied canonical watermark.
- **Raycast adapter:** passes one arbitrary query and configured runtime path to the CLI. It contains
  no retrieval logic or private default paths.

## Data and trust boundaries

The private boundary begins at the query string and SQLite database. Both remain local in version
0.1. The public repository contains only source code and generated synthetic fixtures. The
canonical JSONL writer is outside the process and cannot be invoked through this CLI.

SQLite connections use `mode=ro&immutable=1` plus `PRAGMA query_only = ON`. Output excludes full
records and filesystem paths. A hit includes a short snippet, record type, relevance metadata, and
`jsonl://record/<id>` citation.

## Retrieval flow

1. Normalize up to twelve Unicode word or hyphen tokens.
2. Reject an empty query or invalid limit before opening the database.
3. Open `<runtime>/indexes/vault.sqlite` read-only.
4. Validate `records`, `record_fts`, and `projection_metadata` compatibility.
5. Compare a supplied ledger watermark with projection metadata.
6. Try a full-coverage FTS5 AND query first; use bounded OR retrieval only when no full match exists.
7. Re-rank fallback evidence by term coverage and FTS score.
8. Return a bounded evidence packet or explicit `partial`/`not_found`/`stale` state.

The AND-first path keeps common terms fast on large indexes. Bounded OR fallback preserves recall;
coverage-first re-ranking and the `partial` state prevent a record matching one generic term from
silently becoming a fully supported result.

## Failure model

| State | Meaning | CLI exit |
|---|---|---:|
| `ok` | At least one cited evidence hit | 0 |
| `partial` | Evidence exists, but no record covers every meaningful term | 6 |
| `not_found` | Compatible fresh index, no evidence | 4 |
| `invalid_request` | Empty/unsafe query or invalid option | 2 |
| `unavailable` | Index missing, unreadable, or incompatible | 3 |
| `stale` | Projection watermark differs from the required watermark | 5 |

## Extension points

Optional synthesis must consume the evidence-packet contract, remain disabled by default, and live
behind a tool-less provider boundary. Alternative launchers may call the CLI but must not duplicate
ranking, freshness, or privacy policy.
