"""Versioned SQLite FTS5 policy retrieval with auditable citations."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from launchguard.models import Citation

SUSPICIOUS_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system prompt",
    "reveal secret",
    "environment variable",
    "exfiltrate",
)


@dataclass(frozen=True)
class PolicyDocument:
    document_id: str
    title: str
    market: str
    effective_date: str
    source_path: str
    body: str


def contains_prompt_injection(text: str) -> bool:
    lowered = text.lower()
    return any(pattern in lowered for pattern in SUSPICIOUS_PATTERNS)


def parse_policy(path: Path) -> PolicyDocument:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"Policy is missing YAML-style metadata: {path}")
    _, header, body = raw.split("---", 2)
    metadata: Dict[str, str] = {}
    for line in header.strip().splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"Invalid policy metadata line in {path}: {line}")
        metadata[key.strip()] = value.strip().strip('"')
    required = {"id", "title", "market", "effective_date"}
    missing = required - metadata.keys()
    if missing:
        raise ValueError(f"Policy metadata is missing {sorted(missing)} in {path}")
    if contains_prompt_injection(body):
        raise ValueError(f"Policy contains a prompt-injection pattern: {path}")
    return PolicyDocument(
        document_id=metadata["id"],
        title=metadata["title"],
        market=metadata["market"].upper(),
        effective_date=metadata["effective_date"],
        source_path=str(path),
        body=body.strip(),
    )


def _chunks(body: str) -> Iterable[str]:
    sections = re.split(r"(?=^##\s)", body, flags=re.MULTILINE)
    for section in sections:
        cleaned = section.strip()
        if cleaned:
            yield cleaned


class PolicyIndex:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS policy_chunks USING fts5(
                document_id UNINDEXED,
                title,
                market UNINDEXED,
                effective_date UNINDEXED,
                source_path UNINDEXED,
                chunk,
                tokenize='porter unicode61'
            )
            """
        )

    def rebuild(self, policy_dir: Path) -> int:
        documents = [parse_policy(path) for path in sorted(policy_dir.glob("*.md"))]
        if not documents:
            raise ValueError(f"No policy documents were found in {policy_dir}")
        with self.connection:
            self.connection.execute("DELETE FROM policy_chunks")
            count = 0
            for document in documents:
                for chunk in _chunks(document.body):
                    self.connection.execute(
                        """
                        INSERT INTO policy_chunks(
                            document_id, title, market, effective_date, source_path, chunk
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            document.document_id,
                            document.title,
                            document.market,
                            document.effective_date,
                            document.source_path,
                            chunk,
                        ),
                    )
                    count += 1
        return count

    def search(self, query: str, market: str, limit: int = 5) -> List[Citation]:
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", query.lower())
        if not tokens:
            return []
        fts_query = " OR ".join(f'"{token}"' for token in dict.fromkeys(tokens[:24]))
        rows = self.connection.execute(
            """
            SELECT document_id, title, market, effective_date, source_path, chunk,
                   bm25(policy_chunks) AS rank
            FROM policy_chunks
            WHERE policy_chunks MATCH ? AND (market = ? OR market = 'GLOBAL')
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, market.upper(), limit),
        ).fetchall()
        citations: List[Citation] = []
        for row in rows:
            rank = abs(float(row["rank"]))
            citations.append(
                Citation(
                    document_id=row["document_id"],
                    title=row["title"],
                    market=row["market"],
                    effective_date=row["effective_date"],
                    source_path=row["source_path"],
                    chunk=row["chunk"],
                    score=round(1 / (1 + rank), 6),
                )
            )
        return citations

    def close(self) -> None:
        self.connection.close()


def citation_ids(citations: Iterable[Citation]) -> Tuple[str, ...]:
    return tuple(dict.fromkeys(citation.document_id for citation in citations))
