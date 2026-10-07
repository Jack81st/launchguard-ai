"""SQLite audit ledger for runs, node events, approvals, and delivery receipts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from launchguard.models import DeliveryReceipt, RunEvent, RunRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self.connection:
            self.connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    sku TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL,
                    detail_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    run_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    note TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    run_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );
                """
            )

    def create_run(self, run_id: str, sku: str, state: Dict[str, Any]) -> None:
        now = _now()
        with self.connection:
            self.connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, "running", sku, json.dumps(state), now, now),
            )

    def update_run(self, run_id: str, status: str, state: Dict[str, Any]) -> None:
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE runs SET status=?, state_json=?, updated_at=? WHERE run_id=?",
                (status, json.dumps(state), _now(), run_id),
            )
        if cursor.rowcount != 1:
            raise KeyError(f"Unknown run: {run_id}")

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        row = self.connection.execute(
            "SELECT * FROM runs WHERE run_id=?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return RunRecord(
            run_id=row["run_id"],
            status=row["status"],
            sku=row["sku"],
            state=json.loads(row["state_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_runs(self, limit: int = 50) -> List[RunRecord]:
        rows = self.connection.execute(
            "SELECT * FROM runs ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self.get_run(row["run_id"]) for row in rows if row is not None]  # type: ignore[misc]

    def add_event(self, run_id: str, event: RunEvent) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO events(run_id, node, status, duration_ms, detail_json, occurred_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event.node,
                    event.status,
                    event.duration_ms,
                    json.dumps(event.detail),
                    event.occurred_at,
                ),
            )

    def events(self, run_id: str) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM events WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [
            {
                "node": row["node"],
                "status": row["status"],
                "duration_ms": row["duration_ms"],
                "detail": json.loads(row["detail_json"]),
                "occurred_at": row["occurred_at"],
            }
            for row in rows
        ]

    def save_approval(self, run_id: str, decision: Dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR REPLACE INTO approvals(
                    run_id, action, reviewer, note, decision_json, decided_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    decision["action"],
                    decision["reviewer"],
                    decision.get("note", ""),
                    json.dumps(decision),
                    _now(),
                ),
            )

    def save_delivery(self, receipt: DeliveryReceipt) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO deliveries VALUES (?, ?, ?, ?)",
                (
                    receipt.run_id,
                    receipt.idempotency_key,
                    receipt.model_dump_json(),
                    _now(),
                ),
            )

    def get_delivery(self, run_id: str) -> Optional[DeliveryReceipt]:
        row = self.connection.execute(
            "SELECT receipt_json FROM deliveries WHERE run_id=?", (run_id,)
        ).fetchone()
        return DeliveryReceipt.model_validate_json(row[0]) if row else None

    def close(self) -> None:
        self.connection.close()
