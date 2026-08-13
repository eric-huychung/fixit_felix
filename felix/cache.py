"""SQLite key-value cache keyed by org id."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

Namespace = Literal["describe", "rules", "translations"]


class Cache:
    """Persistent org-scoped cache for describe results, rule metadata, and translations."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                org_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (org_id, namespace, key)
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> Cache:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def set(self, org_id: str, namespace: Namespace, key: str, value: str) -> None:
        """Store a value under ``(org_id, namespace, key)``."""
        self._conn.execute(
            """
            INSERT INTO cache (org_id, namespace, key, value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(org_id, namespace, key) DO UPDATE SET value = excluded.value
            """,
            (org_id, namespace, key, value),
        )
        self._conn.commit()

    def get(self, org_id: str, namespace: Namespace, key: str) -> str | None:
        """Return a cached value, or ``None`` if missing."""
        row = self._conn.execute(
            """
            SELECT value FROM cache
            WHERE org_id = ? AND namespace = ? AND key = ?
            """,
            (org_id, namespace, key),
        ).fetchone()
        return row[0] if row else None

    def delete(self, org_id: str, namespace: Namespace, key: str) -> None:
        """Remove a cached entry if it exists."""
        self._conn.execute(
            """
            DELETE FROM cache
            WHERE org_id = ? AND namespace = ? AND key = ?
            """,
            (org_id, namespace, key),
        )
        self._conn.commit()
