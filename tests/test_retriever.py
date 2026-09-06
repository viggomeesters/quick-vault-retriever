from __future__ import annotations

import hashlib
import json
import sqlite3
import statistics
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from quick_vault_retriever.cli import RetrievalError, label_from_json, main, query_terms, retrieve

from .test_cli import build_runtime


@pytest.mark.parametrize(
    ("record_type", "query", "content"),
    [
        ("decision", "storage decision", "The storage decision keeps JSONL canonical."),
        ("project", "garden planning", "Garden planning starts before the autumn rain."),
        ("event", "conference date", "The conference date is October 12."),
        ("task", "renew passport", "Renew passport before booking the trip."),
        ("source", "research paper", "The research paper explains retrieval evaluation."),
        ("entity", "Alex role", "Alex role is operations lead."),
    ],
)
def test_general_retrieval_supports_multiple_record_types(
    tmp_path: Path, record_type: str, query: str, content: str
) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": f"{record_type}.synthetic.example",
                "record_type": record_type,
                "title": f"Synthetic {record_type}",
                "content": content,
            }
        ],
    )

    payload = retrieve(runtime, query, 5)

    assert payload["status"] == "ok"
    assert payload["hits"][0]["record_type"] == record_type


def test_not_found_returns_no_evidence(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "note.synthetic.example",
                "record_type": "note",
                "title": "Example",
                "content": "A deliberately unrelated synthetic record.",
            }
        ],
    )

    payload = retrieve(runtime, "quantum orchard", 5)

    assert payload["status"] == "not_found"
    assert payload["hits"] == []
    assert payload["count"] == 0


def test_full_term_matches_avoid_broader_partial_results(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "decision.synthetic.full",
                "record_type": "decision",
                "title": "Full match",
                "content": "The migration decision preserves canonical JSONL.",
            },
            {
                "id": "note.synthetic.partial",
                "record_type": "note",
                "title": "Partial match",
                "content": "A migration can require careful preparation.",
            },
        ],
    )

    payload = retrieve(runtime, "migration decision", 5)

    assert payload["status"] == "ok"
    assert [hit["id"] for hit in payload["hits"]] == ["decision.synthetic.full"]


def test_stale_projection_fails_closed(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path, [], sequence=7)
    ledger = runtime / "ledger" / "changes.jsonl"
    ledger.write_text(json.dumps({"sequence": 8}) + "\n", encoding="utf-8")

    with pytest.raises(RetrievalError, match="stale") as caught:
        retrieve(runtime, "project status", 5)

    assert caught.value.status == "stale"
    assert caught.value.exit_code == 5


def test_missing_projection_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RetrievalError, match="missing") as caught:
        retrieve(tmp_path, "project status", 5)

    assert caught.value.status == "unavailable"


def test_empty_meaningless_query_is_rejected_before_database_access(tmp_path: Path) -> None:
    with pytest.raises(RetrievalError, match="meaningful") as caught:
        retrieve(tmp_path, "what is the", 5)

    assert caught.value.status == "invalid_request"


def test_query_syntax_is_reduced_to_safe_literal_tokens() -> None:
    assert query_terms('title:"Road Map" OR project*; DROP TABLE records') == [
        "title",
        "road",
        "map",
        "or",
        "project",
        "drop",
        "table",
        "records",
    ]


def test_retrieval_does_not_change_projection_bytes(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "note.synthetic.read-only",
                "record_type": "note",
                "title": "Read only",
                "content": "Read only retrieval keeps the projection unchanged.",
            }
        ],
    )
    database = runtime / "indexes" / "vault.sqlite"
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    retrieve(runtime, "read only retrieval", 5)

    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert not database.with_name("vault.sqlite-wal").exists()
    assert not database.with_name("vault.sqlite-shm").exists()


def test_evidence_packet_validates_against_public_schema(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "task.synthetic.passport",
                "record_type": "task",
                "title": "Renew passport",
                "content": "Renew passport before the summer trip.",
            }
        ],
    )
    schema_path = Path(__file__).parents[1] / "schemas" / "evidence-packet.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(retrieve(runtime, "renew passport", 5))


def test_warm_synthetic_p95_is_below_one_second(tmp_path: Path) -> None:
    records = [
        {
            "id": f"note.synthetic.{index}",
            "record_type": "note",
            "title": f"Synthetic note {index}",
            "content": f"Project context number {index} with bounded synthetic evidence.",
        }
        for index in range(500)
    ]
    runtime = build_runtime(tmp_path, records)
    retrieve(runtime, "project context", 5)
    durations = []
    for _ in range(25):
        started = time.perf_counter()
        retrieve(runtime, "project context", 5)
        durations.append((time.perf_counter() - started) * 1000)

    p95 = statistics.quantiles(durations, n=20)[18]
    assert p95 < 1000


def test_cli_renders_markdown_evidence(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "event.synthetic.launch",
                "record_type": "event",
                "title": "Launch date",
                "content": "Launch date is October 12.",
            }
        ],
    )

    exit_code = main(["query", "launch date", "--runtime", str(runtime)])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "# Evidence" in output
    assert "jsonl://record/event.synthetic.launch" in output


def test_cli_renders_partial_warning(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "note.synthetic.alpha",
                "record_type": "note",
                "title": "Alpha",
                "content": "Alpha exists alone.",
            }
        ],
    )

    exit_code = main(["query", "alpha beta", "--runtime", str(runtime)])

    output = capsys.readouterr().out
    assert exit_code == 6
    assert "# Partial evidence" in output
    assert "No single record matched" in output


def test_cli_renders_not_found_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    runtime = build_runtime(tmp_path, [])

    exit_code = main(["query", "absent evidence", "--runtime", str(runtime), "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 4
    assert payload["status"] == "not_found"


def test_cli_renders_controlled_error_in_both_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    json_exit = main(["query", "project status", "--runtime", str(tmp_path), "--format", "json"])
    json_payload = json.loads(capsys.readouterr().out)
    markdown_exit = main(["query", "project status", "--runtime", str(tmp_path)])
    markdown = capsys.readouterr().out

    assert json_exit == 3
    assert json_payload["status"] == "unavailable"
    assert markdown_exit == 3
    assert markdown.startswith("# Unavailable")


def test_incompatible_schema_fails_closed(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path, [])
    database = runtime / "indexes" / "vault.sqlite"
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE projection_metadata SET value = ? WHERE key = 'schema_version'",
        (json.dumps("future.schema"),),
    )
    connection.commit()
    connection.close()

    with pytest.raises(RetrievalError, match="unsupported projection schema"):
        retrieve(runtime, "project status", 5)


@pytest.mark.parametrize("ledger_body", ["", "not-json\n", "{}\n"])
def test_invalid_ledger_fails_closed(tmp_path: Path, ledger_body: str) -> None:
    runtime = build_runtime(tmp_path, [])
    (runtime / "ledger" / "changes.jsonl").write_text(ledger_body, encoding="utf-8")

    with pytest.raises(RetrievalError, match="ledger"):
        retrieve(runtime, "project status", 5)


def test_missing_ledger_fails_closed(tmp_path: Path) -> None:
    runtime = build_runtime(tmp_path, [])
    (runtime / "ledger" / "changes.jsonl").unlink()

    with pytest.raises(RetrievalError, match="ledger is missing"):
        retrieve(runtime, "project status", 5)


def test_incompatible_projection_tables_fail_closed(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    (runtime / "indexes").mkdir(parents=True)
    (runtime / "ledger").mkdir()
    (runtime / "indexes" / "vault.sqlite").touch()
    (runtime / "ledger" / "changes.jsonl").write_text('{"sequence": 1}\n', encoding="utf-8")

    with pytest.raises(RetrievalError, match="incompatible"):
        retrieve(runtime, "project status", 5)


def test_label_falls_back_for_malformed_or_unlabeled_record() -> None:
    assert label_from_json("not-json", "record.id") == "record.id"
    assert label_from_json("{}", "record.id") == "record.id"
    assert label_from_json('{"display_name":"Synthetic Person"}', "record.id") == (
        "Synthetic Person"
    )
