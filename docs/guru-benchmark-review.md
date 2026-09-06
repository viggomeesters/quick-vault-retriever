# Guru Benchmark review

This review applies the constitution in
[`viggomeesters/guru-benchmark`](https://github.com/viggomeesters/guru-benchmark), pinned to
`guru-ai-engineer@2026.09` with benchmark date `2026-09-05`. The evaluation was performed on
2026-09-06 against the repository implementation and local verification evidence available at that
time.

The benchmark repository currently publishes the council roster, hard gates, dimensions, schemas,
and aggregation rules, but not compatible versioned evidence snapshots for its seven named expert
lenses. This review therefore uses the benchmark constitution as a design audit while refusing to
invent expert positions or a weighted score.

## Guru Verdict

**Hold** applies only to a claim that this project is fully “Guru Benchmark approved”: the lens
evidence required for that claim is unavailable. The product design itself is a **conditional go**
under the inspectable hard gates because it is tested, read-only, local-first, recoverable from
canonical JSONL, and explicit about abstention and privacy.

## Guru Score

- Current Score: unscored; a weighted median cannot be calculated without compatible lens inputs.
- North Star Score: unscored for the same reason.
- Confidence in the hard-gate review: high for repository-observable behavior.
- Score dispersion: unavailable.
- Hard gates: correctness pass; evidence pass; security/privacy pass; recoverability pass;
  context-fit pass.

Observed evidence includes the CLI tests, immutable query-only SQLite connection, stable evidence
packet schema, explicit failure states, synthetic fixtures, local privacy gate, measured warm
latency, and the thin Raycast adapter. Private vault contents are deliberately excluded.

## Ultimate Design

Keep the product as one narrow local retrieval primitive:

1. Raycast or a shell supplies an arbitrary natural-language query.
2. The CLI verifies projection compatibility and freshness before retrieval.
3. Deterministic FTS5 retrieval returns bounded snippets with stable record citations.
4. Missing, partial, stale, or incompatible evidence remains visible as an explicit state.
5. Any future model synthesis is opt-in, consumes only the evidence packet, and cannot gain write
   authority over the vault.

Non-goals remain canonical writes, a background indexer, an autonomous vault agent, cloud-first
retrieval, or an entity-specific architecture.

## Opheldering

The unresolved issue is evidentiary rather than architectural: the benchmark names seven council
members but does not yet provide compatible versioned lens snapshots. No expert-specific design
claim can therefore be scored responsibly. This does not block publishing or using the retriever;
it blocks only the stronger Guru Benchmark endorsement claim.

## Guru Contributions

| Council member | Role | Contribution | Confidence | Evidence refs |
|---|---|---|---|---|
| Andrew Karpathy | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| Matt Pocock | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| Peter Steinberger | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| Rich Hickey | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| David Heinemeier Hansson | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| Simon Willison | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |
| Mitchell Hashimoto | abstain | No compatible versioned lens snapshot available | unavailable | benchmark roster only |

## Next Moves

1. Keep the deterministic retriever and Raycast adapter as the version 0.1 release boundary.
   Expected evidence: the full local gate and real adapter smoke test pass.
2. Benchmark any future synthesis provider against deterministic retrieval rather than replacing
   it. Expected evidence: measured latency, answer support, abstention, privacy, and cost deltas.
3. Repeat this evaluation when Guru Benchmark publishes integrity-checked lens snapshots.
   Expected evidence: exact lens versions, source references, roles, weights, weighted median, and
   score dispersion.

## Pins & Evidence

- Benchmark: `guru-ai-engineer@2026.09`
- Benchmark as-of: `2026-09-05`
- Evaluation date: `2026-09-06`
- Evidence cutoff: repository state and local verification observed on `2026-09-06`
- Lens versions: unavailable; all seven members abstain
- Product evidence: [`architecture.md`](architecture.md), [`vision.json`](vision.json), CLI tests,
  evidence-packet schema, privacy audit, performance test, and Raycast adapter smoke test
- Unresolved evidence gap: compatible versioned expert-lens snapshots
