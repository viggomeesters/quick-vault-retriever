from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def build_runtime(root: Path, records: list[dict[str, str]], *, sequence: int = 7) -> Path:
    runtime = root / "runtime"
    indexes = runtime / "indexes"
    ledger = runtime / "ledger"
    indexes.mkdir(parents=True)
    ledger.mkdir()
    database = indexes / "vault.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE records(
            id TEXT PRIMARY KEY,
            record_type TEXT NOT NULL,
            privacy TEXT,
            summary TEXT,
            title_hash TEXT,
            searchable_length INTEGER NOT NULL,
            json TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE record_fts USING fts5(
            id UNINDEXED,
            record_type UNINDEXED,
            content,
            tokenize='unicode61'
        );
        CREATE TABLE projection_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """
    )
    connection.executemany(
        "INSERT INTO projection_metadata(key, value) VALUES (?, ?)",
        [
            ("schema_version", json.dumps("jsonl-vault.sqlite-projection.v1")),
            ("ledger_sequence", json.dumps(sequence)),
        ],
    )
    for record in records:
        payload = {
            "id": record["id"],
            "record_type": record["record_type"],
            "title": record["title"],
            "body_text": record["content"],
        }
        connection.execute(
            "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record["id"],
                record["record_type"],
                "private",
                record["content"][:120],
                "synthetic-title-hash",
                len(record["content"]),
                json.dumps(payload),
            ),
        )
        connection.execute(
            "INSERT INTO record_fts(id, record_type, content) VALUES (?, ?, ?)",
            (record["id"], record["record_type"], record["content"]),
        )
    connection.commit()
    connection.close()
    (ledger / "changes.jsonl").write_text(
        json.dumps({"sequence": sequence, "event": "synthetic.commit"}) + "\n",
        encoding="utf-8",
    )
    return runtime


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quick_vault_retriever.cli", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_general_query_returns_bounded_cited_evidence(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "decision.synthetic.migration",
                "record_type": "decision",
                "title": "Migration decision",
                "content": "The migration decision keeps JSONL canonical and SQLite derived.",
            },
            {
                "id": "project.synthetic.garden",
                "record_type": "project",
                "title": "Garden project",
                "content": "Plant the garden beds before autumn.",
            },
        ],
    )

    result = run_cli(
        "query",
        "What was the migration decision?",
        "--runtime",
        str(runtime),
        "--format",
        "json",
        "--limit",
        "1",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema"] == "quick-vault.evidence-packet.v2"
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    assert payload["hits"][0]["id"] == "decision.synthetic.migration"
    assert payload["hits"][0]["citation_uri"] == ("jsonl://record/decision.synthetic.migration")
    assert "migration" in payload["hits"][0]["snippet"].lower()


def test_generic_disjoint_partial_matches_are_not_reported_as_supported(tmp_path: Path) -> None:
    runtime = build_runtime(
        tmp_path,
        [
            {
                "id": "person.synthetic.alex",
                "record_type": "entity",
                "title": "Alex",
                "content": "Alex works on the community garden.",
            },
            {
                "id": "note.synthetic.schedule",
                "record_type": "note",
                "title": "Delivery schedule",
                "content": "The delivery schedule belongs to a different project.",
            },
        ],
    )

    result = run_cli(
        "query",
        "What is Alex's schedule?",
        "--runtime",
        str(runtime),
        "--format",
        "json",
    )

    assert result.returncode == 6
    payload = json.loads(result.stdout)
    assert payload["status"] == "partial"
    assert payload["count"] == 2
    assert max(hit["term_coverage"] for hit in payload["hits"]) == 0.5
