from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict


class HealingLedger:
    """Persist self-healing intervention records for audit and replay."""

    def __init__(self, db_path: str = "exports/healing_ledger.db"):
        """Initialize ledger storage and create schema if needed."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection to the ledger database."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Create the healing events table when missing."""
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS healing_events (
                    action_id TEXT PRIMARY KEY,
                    model_id TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    pre_metrics TEXT,
                    post_metrics TEXT,
                    verification_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def record(
        self,
        action_id: str,
        model_id: str,
        action_type: str,
        pre_metrics: str,
        post_metrics: str,
        verification_status: str,
    ) -> None:
        """Insert or replace one healing event record."""
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO healing_events(
                    action_id, model_id, action_type, pre_metrics, post_metrics, verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    model_id,
                    action_type,
                    pre_metrics,
                    post_metrics,
                    verification_status,
                    datetime.utcnow().isoformat(),
                ),
            )

    def count(self) -> int:
        """Return the total number of healing events persisted."""
        with self._connect() as con:
            cur = con.execute("SELECT COUNT(*) FROM healing_events")
            return int(cur.fetchone()[0])
