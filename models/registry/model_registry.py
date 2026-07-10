from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class ModelRegistry:
    """Persist model versions and track the active deployment version."""

    def __init__(self, db_path: str = "exports/model_registry.db", require_human_approval: bool = False):
        """Initialize registry database and create schema if needed.

        Args:
            db_path: SQLite path for registry metadata.
            require_human_approval: When True, newly registered versions are
                stored in pending state and will not auto-activate until
                approved via ``approve_version``.
        """
        self.db_path = Path(db_path)
        self.require_human_approval = require_human_approval
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Create a new SQLite connection to the registry database."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Create model registry table and unique indexes."""
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS model_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    version_tag TEXT NOT NULL,
                    version_uuid TEXT,
                    file_path TEXT NOT NULL,
                    metrics_json TEXT,
                    created_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    requires_approval INTEGER NOT NULL DEFAULT 0,
                    is_approved INTEGER NOT NULL DEFAULT 1,
                    approved_by TEXT,
                    approved_at TEXT
                )
                """
            )
            columns = [row[1] for row in con.execute("PRAGMA table_info(model_registry)").fetchall()]
            if "version_uuid" not in columns:
                con.execute("ALTER TABLE model_registry ADD COLUMN version_uuid TEXT")
            if "requires_approval" not in columns:
                con.execute("ALTER TABLE model_registry ADD COLUMN requires_approval INTEGER NOT NULL DEFAULT 0")
            if "is_approved" not in columns:
                con.execute("ALTER TABLE model_registry ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1")
            if "approved_by" not in columns:
                con.execute("ALTER TABLE model_registry ADD COLUMN approved_by TEXT")
            if "approved_at" not in columns:
                con.execute("ALTER TABLE model_registry ADD COLUMN approved_at TEXT")
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_model_version ON model_registry(model_name, version_tag)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_active_uuid ON model_registry(model_name, is_active, version_uuid)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_model_pending_approval ON model_registry(model_name, requires_approval, is_approved, created_at)"
            )

    def register(self, model_name: str, file_path: str, metrics_json: str) -> str:
        """Register a new model version.

        In default mode the new version becomes active immediately.
        When ``require_human_approval`` is enabled, the version is stored as
        pending and existing active versions remain unchanged.
        """
        version_tag = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        version_uuid = str(uuid.uuid4())
        requires_approval = 1 if self.require_human_approval else 0
        is_approved = 0 if self.require_human_approval else 1
        is_active = 0 if self.require_human_approval else 1
        with self._connect() as con:
            if not self.require_human_approval:
                con.execute("UPDATE model_registry SET is_active = 0 WHERE model_name = ?", (model_name,))
            con.execute(
                """
                INSERT INTO model_registry(
                    model_name,
                    version_tag,
                    version_uuid,
                    file_path,
                    metrics_json,
                    created_at,
                    is_active,
                    requires_approval,
                    is_approved,
                    approved_by,
                    approved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_name,
                    version_tag,
                    version_uuid,
                    file_path,
                    metrics_json,
                    datetime.utcnow().isoformat(),
                    is_active,
                    requires_approval,
                    is_approved,
                    None,
                    None,
                ),
            )
        return version_tag

    def active_version(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Return metadata for the currently active version of a model."""
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT model_name, version_tag, version_uuid, file_path, metrics_json, created_at
                FROM model_registry
                WHERE model_name = ? AND is_active = 1
                ORDER BY id DESC LIMIT 1
                """,
                (model_name,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "model_name": row[0],
            "version_tag": row[1],
            "version_uuid": row[2],
            "file_path": row[3],
            "metrics_json": row[4],
            "created_at": row[5],
        }

    def get_active_version(self, model_name: str) -> Tuple[str, str]:
        """Return (version_uuid, file_path) for the active model version."""
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT version_uuid, file_path
                FROM model_registry
                WHERE model_name = ? AND is_active = 1
                ORDER BY id DESC LIMIT 1
                """,
                (model_name,),
            )
            row = cur.fetchone()
        if not row:
            return "", ""
        return (row[0] or "", row[1] or "")

    def rollback_to_version(self, model_name: str, version_tag: str) -> bool:
        """Set an existing model version as active and deactivate others."""
        with self._connect() as con:
            cur = con.execute(
                "SELECT id FROM model_registry WHERE model_name = ? AND version_tag = ?",
                (model_name, version_tag),
            )
            row = cur.fetchone()
            if not row:
                return False
            con.execute("UPDATE model_registry SET is_active = 0 WHERE model_name = ?", (model_name,))
            con.execute(
                "UPDATE model_registry SET is_active = 1, is_approved = 1, approved_at = COALESCE(approved_at, ?), approved_by = COALESCE(approved_by, ?) WHERE id = ?",
                (datetime.utcnow().isoformat(), "rollback", row[0]),
            )
            return True

    def approve_version(self, model_name: str, version_tag: str, approved_by: str = "human") -> bool:
        """Approve a pending model version and make it active.

        Args:
            model_name: Logical model identifier.
            version_tag: Registered version tag to activate.
            approved_by: Free-text approver identity for audit records.
        """
        approval_ts = datetime.utcnow().isoformat()
        with self._connect() as con:
            cur = con.execute(
                "SELECT id FROM model_registry WHERE model_name = ? AND version_tag = ?",
                (model_name, version_tag),
            )
            row = cur.fetchone()
            if not row:
                return False

            con.execute("UPDATE model_registry SET is_active = 0 WHERE model_name = ?", (model_name,))
            con.execute(
                """
                UPDATE model_registry
                SET is_active = 1,
                    is_approved = 1,
                    approved_by = ?,
                    approved_at = ?,
                    requires_approval = 1
                WHERE id = ?
                """,
                (approved_by, approval_ts, row[0]),
            )
            return True
