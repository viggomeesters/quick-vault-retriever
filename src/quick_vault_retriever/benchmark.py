"""Private-fixture benchmark runner with aggregate-only output."""

from __future__ import annotations

import json
import math
import statistics
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from quick_vault_retriever.errors import RetrievalError

if TYPE_CHECKING:
    from pathlib import Path

BENCHMARK_SCHEMA = "quick-vault.benchmark-report.v1"
MAX_CASES = 1000
Retriever = Callable[["Path", str, int], dict[str, Any]]


def percentile(values: list[float], fraction: float) -> float:
    """Return a nearest-rank percentile for a non-empty sample."""
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def rate(correct: int, total: int) -> float | None:
    """Return a rounded rate or null when the metric was not evaluated."""
    return round(correct / total, 3) if total else None


def load_cases(fixtures: Path) -> list[dict[str, Any]]:
    """Load the narrow fixture contract without echoing private values in errors."""
    try:
        lines = fixtures.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise RetrievalError("invalid_request", "benchmark fixture is unavailable", 2) from error
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
            valid = (
                isinstance(case, dict)
                and set(case) == {"query", "expected_status", "expected_citations"}
                and isinstance(case["query"], str)
                and bool(case["query"].strip())
                and case["expected_status"] in {"ok", "partial", "not_found"}
                and isinstance(case["expected_citations"], list)
                and all(
                    isinstance(citation, str) and citation.startswith("jsonl://record/")
                    for citation in case["expected_citations"]
                )
            )
        except (json.JSONDecodeError, TypeError):
            valid = False
            case = {}
        if not valid:
            raise RetrievalError(
                "invalid_request",
                f"benchmark fixture is invalid at line {line_number}",
                2,
            )
        cases.append(case)
        if len(cases) > MAX_CASES:
            raise RetrievalError(
                "invalid_request",
                f"benchmark fixture exceeds {MAX_CASES} cases",
                2,
            )
    if not cases:
        raise RetrievalError("invalid_request", "benchmark fixture contains no cases", 2)
    return cases


def run_benchmark(
    runtime: Path,
    fixtures: Path,
    *,
    repeat: int,
    limit: int,
    retriever: Retriever,
) -> dict[str, Any]:
    """Run private queries and return only redacted aggregate measurements."""
    cases = load_cases(fixtures)
    durations: list[float] = []
    status_correct = 0
    aligned = alignment_cases = 0
    ambiguity_correct = ambiguity_cases = 0
    abstention_correct = abstention_cases = 0
    for case in cases:
        result: dict[str, Any] = {}
        for _ in range(repeat):
            result = retriever(runtime, str(case["query"]), limit)
            durations.append(float(result["elapsed_ms"]))
        actual = {str(hit["citation_uri"]) for hit in result["hits"]}
        expected = {str(citation) for citation in case["expected_citations"]}
        expected_status = str(case["expected_status"])
        actual_status = str(result["status"])
        status_correct += actual_status == expected_status
        if expected:
            alignment_cases += 1
            aligned += expected.issubset(actual)
        if expected_status == "partial":
            ambiguity_cases += 1
            ambiguity_correct += actual_status == "partial"
        if expected_status == "not_found":
            abstention_cases += 1
            abstention_correct += actual_status == "not_found"

    return {
        "schema": BENCHMARK_SCHEMA,
        "case_count": len(cases),
        "sample_count": len(durations),
        "latency_ms": {
            "p50": round(statistics.median(durations), 3),
            "p95": round(percentile(durations, 0.95), 3),
        },
        "metrics": {
            "status_accuracy": rate(status_correct, len(cases)),
            "source_alignment_rate": rate(aligned, alignment_cases),
            "ambiguity_accuracy": rate(ambiguity_correct, ambiguity_cases),
            "abstention_accuracy": rate(abstention_correct, abstention_cases),
        },
        "evaluation_counts": {
            "status": len(cases),
            "source_alignment": alignment_cases,
            "ambiguity": ambiguity_cases,
            "abstention": abstention_cases,
        },
    }
