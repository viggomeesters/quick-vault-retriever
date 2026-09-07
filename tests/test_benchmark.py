from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from jsonschema import Draft202012Validator

from quick_vault_retriever.cli import main

from .test_cli import build_runtime

if TYPE_CHECKING:
    import pytest


def write_fixtures(path: Path, cases: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(case) + "\n" for case in cases),
        encoding="utf-8",
    )


def test_benchmark_emits_only_redacted_aggregate_metrics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_query = "private migration phrase"
    private_citation = "jsonl://record/decision.synthetic.migration"
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "decision.synthetic.migration",
                "record_type": "decision",
                "title": "Migration decision",
                "content": "The private migration phrase keeps JSONL canonical.",
            }
        ],
    )
    fixtures = tmp_path / "private-evaluation.jsonl"
    write_fixtures(
        fixtures,
        [
            {
                "query": private_query,
                "expected_status": "ok",
                "expected_citations": [private_citation],
            }
        ],
    )

    exit_code = main(
        [
            "benchmark",
            "--runtime",
            str(runtime),
            "--fixtures",
            str(fixtures),
            "--repeat",
            "2",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    report = json.loads(output)
    schema_path = Path(__file__).parents[1] / "schemas" / "benchmark-report.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(report)
    assert report["schema"] == "quick-vault.benchmark-report.v1"
    assert report["case_count"] == 1
    assert report["sample_count"] == 2
    assert report["metrics"]["source_alignment_rate"] == 1.0
    assert report["latency_ms"]["p50"] >= 0
    assert report["latency_ms"]["p95"] >= report["latency_ms"]["p50"]
    assert private_query not in output
    assert private_citation not in output
    assert str(fixtures) not in output


def test_benchmark_measures_status_ambiguity_and_abstention(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "decision.synthetic.migration",
                "record_type": "decision",
                "title": "Migration decision",
                "content": "The migration decision keeps JSONL canonical.",
            },
            {
                "id": "entity.synthetic.alex",
                "record_type": "entity",
                "title": "Alex",
                "content": "Alex works on the community garden.",
            },
            {
                "id": "note.synthetic.address",
                "record_type": "note",
                "title": "Address",
                "content": "The delivery address belongs to another project.",
            },
        ],
    )
    fixtures = tmp_path / "quality.jsonl"
    write_fixtures(
        fixtures,
        [
            {
                "query": "migration decision",
                "expected_status": "ok",
                "expected_citations": ["jsonl://record/decision.synthetic.migration"],
            },
            {
                "query": "Alex project",
                "expected_status": "partial",
                "expected_citations": [],
            },
            {
                "query": "quantum orchard",
                "expected_status": "not_found",
                "expected_citations": [],
            },
        ],
    )

    exit_code = main(
        [
            "benchmark",
            "--runtime",
            str(runtime),
            "--fixtures",
            str(fixtures),
            "--repeat",
            "1",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["metrics"] == {
        "status_accuracy": 1.0,
        "source_alignment_rate": 1.0,
        "ambiguity_accuracy": 1.0,
        "abstention_accuracy": 1.0,
    }
    assert report["evaluation_counts"] == {
        "status": 3,
        "source_alignment": 1,
        "ambiguity": 1,
        "abstention": 1,
    }


def test_benchmark_rejects_invalid_private_fixture_without_echoing_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    private_text = "not-json-private-question"
    fixtures = tmp_path / "invalid.jsonl"
    fixtures.write_text(private_text + "\n", encoding="utf-8")

    exit_code = main(
        [
            "benchmark",
            "--runtime",
            str(tmp_path),
            "--fixtures",
            str(fixtures),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    payload = json.loads(captured.out)
    schema_path = Path(__file__).parents[1] / "schemas" / "benchmark-report.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)
    assert payload == {
        "schema": "quick-vault.benchmark-report.v1",
        "status": "invalid_request",
        "message": "benchmark fixture is invalid at line 1",
    }
    assert private_text not in captured.out
    assert "Traceback" not in captured.err


def test_benchmark_rejects_an_unbounded_case_corpus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixtures = tmp_path / "too-many.jsonl"
    case = {
        "query": "bounded query",
        "expected_status": "not_found",
        "expected_citations": [],
    }
    write_fixtures(fixtures, [case] * 1001)

    exit_code = main(
        [
            "benchmark",
            "--runtime",
            str(tmp_path),
            "--fixtures",
            str(fixtures),
        ]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["message"] == "benchmark fixture exceeds 1000 cases"
