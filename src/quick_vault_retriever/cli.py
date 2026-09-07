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

from quick_vault_retriever.benchmark import BENCHMARK_SCHEMA, run_benchmark
from quick_vault_retriever.errors import RetrievalError

SCHEMA = "quick-vault.evidence-packet.v2"
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
ADDRESS_INTENT_TERMS = frozenset({"adres", "address", "woonadres"})
ADDRESS_PATTERN = re.compile(
    r"\b[\w'.-]+(?:straat|laan|weg|plein|gracht|singel|kade|dreef|hof|park|pad|"
    r"steeg|markt|boulevard|street|road|avenue|drive)\s+\d{1,5}[a-z]?"
    r"(?:[-/]\d+[a-z]?)?\b",
    flags=re.IGNORECASE,
)
RETRIEVAL_SQL = """
    SELECT f.id, f.record_type, f.content, r.json,
           bm25(record_fts) AS score,
           snippet(record_fts, 2, '**', '**', ' … ', 36) AS snippet
    FROM record_fts AS f
    JOIN records AS r ON r.id = f.id
    WHERE record_fts MATCH ?
    ORDER BY score
    LIMIT ?
    """
ADDRESS_RETRIEVAL_SQL = """
    SELECT f.id, f.record_type, f.content, r.json,
           bm25(record_fts) AS score,
           snippet(record_fts, 2, '**', '**', ' … ', 36) AS snippet
    FROM record_fts AS f
    JOIN records AS r ON r.id = f.id
    WHERE record_fts MATCH ?
      AND (
        f.content LIKE '%straat %' OR f.content LIKE '%laan %'
        OR f.content LIKE '%weg %' OR f.content LIKE '%plein %'
        OR f.content LIKE '%gracht %' OR f.content LIKE '%singel %'
        OR f.content LIKE '%kade %' OR f.content LIKE '%dreef %'
        OR f.content LIKE '%hof %' OR f.content LIKE '%park %'
        OR f.content LIKE '%pad %' OR f.content LIKE '%steeg %'
        OR f.content LIKE '%markt %' OR f.content LIKE '%boulevard %'
        OR f.content LIKE '%street %' OR f.content LIKE '%road %'
        OR f.content LIKE '%avenue %' OR f.content LIKE '%drive %'
      )
    ORDER BY score
    LIMIT ?
    """


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


def address_subject_terms(terms: list[str]) -> list[str]:
    """Return the bounded subject terms for an explicit address question."""
    if not ADDRESS_INTENT_TERMS.intersection(terms):
        return []
    return [term for term in terms if term not in ADDRESS_INTENT_TERMS]


def find_address_candidates(
    rows: list[sqlite3.Row], subject_terms: list[str]
) -> list[tuple[int, float, str, str, str, sqlite3.Row]]:
    """Find and rank street addresses near subject terms in bounded rows."""
    candidates: list[tuple[int, float, str, str, str, sqlite3.Row]] = []
    for row in rows:
        content = str(row["content"] or "")
        folded = content.casefold()
        subject_positions = [
            match.start()
            for term in subject_terms
            for match in re.finditer(re.escape(term), folded, flags=re.IGNORECASE)
        ]
        if not subject_positions:
            continue
        for match in ADDRESS_PATTERN.finditer(content):
            address = match.group(0).strip()
            proximity = min(abs(match.start() - position) for position in subject_positions)
            candidates.append(
                (
                    proximity,
                    float(row["score"]),
                    str(row["id"]),
                    address.casefold(),
                    address,
                    row,
                )
            )
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return candidates


def address_context(content: str, address: str) -> str:
    """Return bounded local context centered on one extracted address."""
    position = content.casefold().find(address.casefold())
    start = max(0, position - 160)
    end = min(len(content), position + len(address) + 160)
    context = content[start:end].strip()
    highlighted = re.sub(
        re.escape(address), f"**{address}**", context, count=1, flags=re.IGNORECASE
    )
    return f"{'… ' if start else ''}{highlighted}{' …' if end < len(content) else ''}"[:800]


def address_hits(
    candidates: list[tuple[int, float, str, str, str, sqlite3.Row]],
    matched_terms: list[str],
    term_coverage: float,
    limit: int,
) -> list[dict[str, Any]]:
    """Render address candidates as bounded cited evidence hits."""
    hits: list[dict[str, Any]] = []
    for _, score, _, _, address, row in candidates[:limit]:
        record_id = str(row["id"])
        hits.append(
            {
                "id": record_id,
                "record_type": str(row["record_type"]),
                "label": label_from_json(str(row["json"]), record_id),
                "citation_uri": f"jsonl://record/{record_id}",
                "snippet": address_context(str(row["content"] or ""), address),
                "matched_terms": matched_terms,
                "term_coverage": term_coverage,
                "score": round(score, 6),
            }
        )
    return hits


def address_evidence(
    rows: list[sqlite3.Row], subject_terms: list[str], original_terms: list[str], limit: int
) -> tuple[dict[str, str] | None, list[dict[str, Any]]]:
    """Extract the closest cited street address from bounded subject evidence."""
    candidates = find_address_candidates(rows, subject_terms)
    if not candidates:
        return None, []
    if len({candidate[3] for candidate in candidates}) > 1:
        return broad_address_evidence(rows, subject_terms, original_terms, limit)

    selected_address = candidates[0][3]
    supporting = [candidate for candidate in candidates if candidate[3] == selected_address]
    hits = address_hits(supporting, original_terms, 1.0, limit)
    answer: dict[str, str] = {
        "kind": "extracted_value",
        "field": "address",
        "text": supporting[0][4],
        "citation_uri": str(hits[0]["citation_uri"]),
    }
    return answer, hits


def broad_address_evidence(
    rows: list[sqlite3.Row], subject_terms: list[str], original_terms: list[str], limit: int
) -> tuple[None, list[dict[str, Any]]]:
    """Return distinct address candidates without guessing among them."""
    distinct = []
    seen = set()
    for candidate in find_address_candidates(rows, subject_terms):
        normalized_address = candidate[3]
        if normalized_address not in seen:
            seen.add(normalized_address)
            distinct.append(candidate)
    coverage = round(len(subject_terms) / len(original_terms), 3)
    return None, address_hits(distinct, subject_terms, coverage, limit)


def fetch_rows(
    connection: sqlite3.Connection,
    terms: list[str],
    candidate_limit: int,
    *,
    operator: str | None = None,
) -> list[sqlite3.Row]:
    """Fetch bounded full-coverage rows, falling back to OR only when needed."""
    if operator is not None:
        return connection.execute(
            RETRIEVAL_SQL, (fts_query(terms, operator), candidate_limit)
        ).fetchall()
    rows = connection.execute(RETRIEVAL_SQL, (fts_query(terms, "AND"), candidate_limit)).fetchall()
    if rows:
        return rows
    return connection.execute(RETRIEVAL_SQL, (fts_query(terms), candidate_limit)).fetchall()


def fetch_address_rows(
    connection: sqlite3.Connection, terms: list[str], candidate_limit: int
) -> list[sqlite3.Row]:
    """Fetch bounded subject rows whose text can contain a street address."""
    return connection.execute(ADDRESS_RETRIEVAL_SQL, (fts_query(terms), candidate_limit)).fetchall()


def lexical_evidence(rows: list[sqlite3.Row], terms: list[str], limit: int) -> list[dict[str, Any]]:
    """Rank bounded lexical rows by coverage and FTS score."""
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
    return hits


def query_evidence(
    connection: sqlite3.Connection, terms: list[str], limit: int
) -> tuple[dict[str, str] | None, list[dict[str, Any]]]:
    """Choose the bounded property or generic lexical retrieval path."""
    candidate_limit = min(max(limit * 8, 24), 160)
    subject_terms = address_subject_terms(terms)
    if subject_terms:
        rows = fetch_rows(connection, subject_terms, 160, operator="AND")
        if len(subject_terms) > 1:
            seen_ids = {str(row["id"]) for row in rows}
            rows.extend(
                row
                for row in fetch_address_rows(connection, subject_terms, 160)
                if str(row["id"]) not in seen_ids
            )
        return address_evidence(rows, subject_terms, terms, limit)
    return None, lexical_evidence(fetch_rows(connection, terms, candidate_limit), terms, limit)


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

        answer, hits = query_evidence(connection, terms, limit)
    except sqlite3.Error as error:
        raise RetrievalError("unavailable", "vault projection is incompatible", 3) from error
    finally:
        if "connection" in locals():
            connection.close()

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
        "answer": answer,
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
    benchmark = subcommands.add_parser("benchmark", help="measure retrieval with private fixtures")
    benchmark.add_argument("--runtime", type=Path)
    benchmark.add_argument("--fixtures", type=Path, required=True)
    benchmark.add_argument("--repeat", type=int, choices=range(1, 101), default=3, metavar="1..100")
    benchmark.add_argument("--limit", type=int, choices=range(1, 21), default=5, metavar="1..20")
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
    if result.get("answer"):
        answer = result["answer"]
        return "\n".join(
            [
                "# Answer",
                "",
                f"**{answer['text']}**",
                "",
                f"Source: `{answer['citation_uri']}`",
                "",
                f"Fresh at ledger sequence {result['freshness']['projection_sequence']}.",
            ]
        )
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
        if args.command == "benchmark":
            report = run_benchmark(
                configured_runtime(args.runtime),
                args.fixtures.expanduser(),
                repeat=args.repeat,
                limit=args.limit,
                retriever=retrieve,
            )
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0
        result = retrieve(configured_runtime(args.runtime), args.query, args.limit)
        output = (
            json.dumps(result, ensure_ascii=False, sort_keys=True)
            if args.format == "json"
            else render_markdown(result)
        )
        print(output)
        return {"ok": 0, "not_found": 4, "partial": 6}[result["status"]]
    except RetrievalError as error:
        if args.command == "benchmark":
            print(
                json.dumps(
                    {
                        "schema": BENCHMARK_SCHEMA,
                        "status": error.status,
                        "message": str(error),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return error.exit_code
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
