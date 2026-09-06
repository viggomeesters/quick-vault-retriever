# Private retrieval benchmarking

The benchmark command measures the deterministic retriever against a local JSONL case file. It is
intended for personal questions and expected citations that must never enter the public repository.

## Fixture boundary

Store cases under `private-fixtures/`, which is excluded by `.gitignore`. Each non-empty line is one
strict JSON object:

```json
{"query":"Which decision did we make about the example migration?","expected_status":"ok","expected_citations":["jsonl://record/decision.synthetic.example"]}
```

Only these fields are accepted:

- `query`: a non-empty natural-language question;
- `expected_status`: `ok`, `partial`, or `not_found`;
- `expected_citations`: zero or more complete `jsonl://record/...` identifiers.

Do not add answers, notes, names, fixture labels, or commentary. Invalid lines fail with a line
number but never echo their contents. A run accepts at most 1,000 cases; `--repeat` is limited to
100 and the retrieval result limit to 20 so an accidental corpus cannot become an unbounded job.

## Run

```bash
uv run quick-vault benchmark \
  --runtime /path/to/jsonl-vault/default \
  --fixtures private-fixtures/retrieval.jsonl \
  --repeat 5 \
  --limit 5
```

The runtime can also come from `QUICK_VAULT_RUNTIME` or the private user configuration documented
in [Raycast setup](raycast.md). The command reads the projection through the same immutable,
query-only retrieval path as normal queries.

## Output contract

The only output is one `quick-vault.benchmark-report.v1` JSON object validated by
[`benchmark-report.schema.json`](../schemas/benchmark-report.schema.json). A successful report
contains:

- case and measurement counts;
- p50 and nearest-rank p95 retrieval latency in milliseconds;
- status accuracy across all cases;
- source alignment across cases with one or more expected citations;
- ambiguity accuracy for cases expected to return `partial`;
- abstention accuracy for cases expected to return `not_found`.

A category that has no evaluable cases is reported as `null`, with a corresponding count of zero.
Source alignment means that every expected citation appeared in the bounded result. It measures
citation recall for the labeled set; it does not claim that every additional hit is relevant.

The report deliberately excludes queries, answers, query hashes, citations, fixture paths,
per-case results, timestamps, and host information. The command has no output-file option and does
not persist a benchmark report. Redirecting stdout is an explicit caller choice; `benchmark-results/`
is ignored as an additional safeguard.

## Building a useful corpus

Use a small balanced set rather than hundreds of near-duplicate contact lookups. Include:

- supported questions across decisions, projects, events, tasks, sources, and entities;
- ambiguous questions whose terms occur in different records;
- questions for which the correct behavior is abstention;
- common short questions and broader multi-term questions;
- cases that exercise the configured result limit.

Re-run the same pinned fixture before and after a retrieval change. Compare the aggregate report,
but inspect any regression locally against the source records before accepting the change.
