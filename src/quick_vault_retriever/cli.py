"""Command-line interface for Quick Vault Retriever."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

SCHEMA = "quick-vault.evidence-packet.v1"
PROJECTION_SCHEMA = "jsonl-vault.sqlite-projection.v1"
MIN_TOKEN_LENGTH = 2
STOPWORDS = {
    "a",
    "aan",
    "de",
    "een",
    "en",
    "het",
    "hoe",
    "i",
    "in",
    "is",
    "of",
    "op",
    "the",
    "to",
    "van",
    "was",
    "wat",
    "we",
    "what",
    "when",
    "where",
    "who",
    "why",
}


class RetrievalError(Exception):
    """A controlled retrieval failure with a public result state."""

    def __init__(self, status: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.status = status
        self.exit_code = exit_code


def query_terms(query: str) -> list[str]:
    """Return bounded, meaningful Unicode tokens without query syntax."""
    tokens = re.findall(r"[\w-]+", query.casefold(), flags=re.UNICODE)
    meaningful = [
        token for token in tokens if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    ]
    return list(dict.fromkeys(meaningful))[:12]


def fts_query(terms: list[str], operator: str = "OR") -> str:
    """Build a quoted FTS expression from already sanitized tokens."""
    separator = f" {operator} "
    return separator.join(f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms)


def metadata_value(connection: sqlite3.Connection, key: str) -> Any:
    """Read and JSON-decode one projection metadata value."""
    row = connection.execute(
        "SELECT value FROM projection_metadata WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        raise RetrievalError("unavailable", f"projection metadata missing: {key}", 3)
    try:
        return json.loads(str(row[0]))
    except json.JSONDecodeError:
        return row[0]


def canonical_sequence(runtime: Path) -> int:
    """Read the last committed ledger sequence without loading the ledger."""
    ledger = runtime / "ledger" / "changes.jsonl"
    if not ledger.is_file():
        raise RetrievalError("unavailable", "canonical ledger is missing", 3)
    with ledger.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        buffer = b""
        while position > 0 and b"\n" not in buffer.rstrip(b"\n"):
            size = min(4096, position)
            position -= size
            handle.seek(position)
            buffer = handle.read(size) + buffer
    lines = [line for line in buffer.splitlines() if line.strip()]
    if not lines:
        raise RetrievalError("unavailable", "canonical ledger is empty", 3)
    try:
        sequence = json.loads(lines[-1])["sequence"]
        return int(sequence)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise RetrievalError("unavailable", "canonical ledger tail is invalid", 3) from error


def label_from_json(raw: str, fallback: str) -> str:
    """Extract a compact label without exposing a full record."""
    try:
        record = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    for key in ("title", "display_name", "canonical_name", "statement", "summary"):
        value = str(record.get(key) or "").replace("\n", " ").strip()
        if value:
            return value[:160]
    return fallback


def retrieve(runtime: Path, query: str, limit: int) -> dict[str, Any]:
    """Retrieve bounded evidence from a compatible fresh runtime projection."""
    started = time.perf_counter()
    terms = query_terms(query)
    if not terms:
        raise RetrievalError("invalid_request", "query has no meaningful searchable terms", 2)
    database = runtime / "indexes" / "vault.sqlite"
    if not database.is_file():
        raise RetrievalError("unavailable", "vault SQLite projection is missing", 3)

    uri = f"file:{database.resolve()}?mode=ro&immutable=1"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=1)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        schema = metadata_value(connection, "schema_version")
        projection_sequence = int(metadata_value(connection, "ledger_sequence"))
        ledger_sequence = canonical_sequence(runtime)
        if schema != PROJECTION_SCHEMA:
            raise RetrievalError("unavailable", "unsupported projection schema", 3)
        if projection_sequence != ledger_sequence:
            raise RetrievalError("stale", "vault projection is stale", 5)

        candidate_limit = min(max(limit * 8, 24), 160)
        sql = """
            SELECT f.id, f.record_type, f.content, r.json,
                   bm25(record_fts) AS score,
                   snippet(record_fts, 2, '**', '**', ' … ', 36) AS snippet
            FROM record_fts AS f
            JOIN records AS r ON r.id = f.id
            WHERE record_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """
        rows = connection.execute(sql, (fts_query(terms, "AND"), candidate_limit)).fetchall()
        if not rows:
            rows = connection.execute(sql, (fts_query(terms), candidate_limit)).fetchall()
    except sqlite3.Error as error:
        raise RetrievalError("unavailable", "vault projection is incompatible", 3) from error
    finally:
        if "connection" in locals():
            connection.close()

    ranked: list[tuple[int, float, sqlite3.Row, list[str]]] = []
    for row in rows:
        content = str(row["content"] or "").casefold()
        matched = [term for term in terms if term in content]
        ranked.append((len(matched), float(row["score"]), row, matched))
    ranked.sort(key=lambda item: (-item[0], item[1], str(item[2]["id"])))

    hits = []
    for coverage, score, row, matched in ranked[:limit]:
        record_id = str(row["id"])
        hits.append(
            {
                "id": record_id,
                "record_type": str(row["record_type"]),
                "label": label_from_json(str(row["json"]), record_id),
                "citation_uri": f"jsonl://record/{record_id}",
                "snippet": str(row["snippet"] or "").strip()[:800],
                "matched_terms": matched,
                "term_coverage": round(coverage / len(terms), 3),
                "score": round(score, 6),
            }
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    best_coverage = hits[0]["term_coverage"] if hits else 0.0
    status = "ok" if best_coverage == 1.0 else "partial" if hits else "not_found"
    return {
        "schema": SCHEMA,
        "status": status,
        "query_hash": hashlib.sha256(query.encode()).hexdigest()[:16],
        "terms": terms,
        "count": len(hits),
        "limit": limit,
        "freshness": {
            "status": "fresh",
            "projection_sequence": projection_sequence,
            "canonical_sequence": ledger_sequence,
        },
        "elapsed_ms": elapsed_ms,
        "hits": hits,
    }


def parser() -> argparse.ArgumentParser:
    """Build the public command parser."""
    root = argparse.ArgumentParser(prog="quick-vault", description=__doc__)
    subcommands = root.add_subparsers(dest="command", required=True)
    query = subcommands.add_parser("query", help="retrieve bounded evidence")
    query.add_argument("query")
    query.add_argument("--runtime", type=Path)
    query.add_argument("--format", choices=("json", "markdown"), default="markdown")
    query.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1..20")
    return root


def configured_runtime(cli_value: Path | None) -> Path:
    """Resolve runtime from the CLI, environment, or private user config."""
    if cli_value is not None:
        return cli_value.expanduser()
    environment = os.environ.get("QUICK_VAULT_RUNTIME", "").strip()
    if environment:
        return Path(environment).expanduser()
    config_path = Path(
        os.environ.get(
            "QUICK_VAULT_CONFIG",
            "~/.config/quick-vault-retriever/config.json",
        )
    ).expanduser()
    if config_path.is_file():
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            runtime = str(payload.get("runtime") or "").strip()
        except (json.JSONDecodeError, OSError) as error:
            raise RetrievalError("invalid_request", "runtime config is invalid", 2) from error
        if runtime:
            return Path(runtime).expanduser()
    raise RetrievalError(
        "invalid_request",
        "runtime is required via --runtime, QUICK_VAULT_RUNTIME, or private config",
        2,
    )


def render_markdown(result: dict[str, Any]) -> str:
    """Render compact human-facing Markdown."""
    if result["status"] == "not_found":
        return "# No evidence found\n\nThe fresh local index contained no matching records."
    heading = "Partial evidence" if result["status"] == "partial" else "Evidence"
    lines = [f"# {heading} · {result['count']} hit(s)", ""]
    if result["status"] == "partial":
        lines.extend(["No single record matched every meaningful query term.", ""])
    for hit in result["hits"]:
        lines.extend(
            [
                f"## {hit['label']}",
                str(hit["snippet"]),
                f"Source: `{hit['citation_uri']}` · coverage {hit['term_coverage']:.0%}",
                "",
            ]
        )
    lines.append(f"Fresh at ledger sequence {result['freshness']['canonical_sequence']}.")
    return "\n".join(lines)


def error_payload(error: RetrievalError) -> dict[str, Any]:
    """Convert a controlled failure to the public evidence schema."""
    return {"schema": SCHEMA, "status": error.status, "message": str(error), "hits": []}


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return its stable exit code."""
    args = parser().parse_args(argv)
    try:
        result = retrieve(configured_runtime(args.runtime), args.query, args.limit)
        output = (
            json.dumps(result, ensure_ascii=False, sort_keys=True)
            if args.format == "json"
            else render_markdown(result)
        )
        print(output)
        return {"ok": 0, "not_found": 4, "partial": 6}[result["status"]]
    except RetrievalError as error:
        payload = error_payload(error)
        output = (
            json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if args.format == "json"
            else f"# {error.status.replace('_', ' ').title()}\n\n{error}"
        )
        print(output)
        return error.exit_code


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess contract test
    sys.exit(main())
