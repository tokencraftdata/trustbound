"""Atomic spend/replay ledger used by all stateful configurations."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from .models import Decision


class AtomicLedger:
    """SQLite ledger with one serializable reservation transaction per attempt."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS itinerary (id TEXT PRIMARY KEY, limit_minor INTEGER NOT NULL, spent_minor INTEGER NOT NULL DEFAULT 0)"
        )
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS decision (transaction_id TEXT PRIMARY KEY, itinerary_id TEXT NOT NULL, amount_minor INTEGER NOT NULL)"
        )
        self._connection.commit()

    def initialize(self, itinerary_id: str, limit_minor: int) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT OR IGNORE INTO itinerary(id, limit_minor, spent_minor) VALUES (?, ?, 0)",
                (itinerary_id, limit_minor),
            )
            self._connection.commit()

    def context(self, itinerary_id: str) -> tuple[int, int]:
        with self._lock:
            row = self._connection.execute(
                "SELECT spent_minor, (SELECT COUNT(*) FROM decision WHERE itinerary_id = ?) FROM itinerary WHERE id = ?",
                (itinerary_id, itinerary_id),
            ).fetchone()
        if row is None:
            raise KeyError(itinerary_id)
        return int(row[0]), int(row[1])

    def reserve(self, itinerary_id: str, transaction_id: str, amount_minor: int) -> Decision:
        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                if connection.execute(
                    "SELECT 1 FROM decision WHERE transaction_id = ?", (transaction_id,)
                ).fetchone():
                    connection.rollback()
                    return Decision(False, "replay")
                row = connection.execute(
                    "SELECT limit_minor, spent_minor FROM itinerary WHERE id = ?",
                    (itinerary_id,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    return Decision(False, "unknown_itinerary")
                limit_minor, spent_minor = map(int, row)
                if spent_minor + amount_minor > limit_minor:
                    connection.rollback()
                    return Decision(False, "aggregate_budget")
                connection.execute(
                    "INSERT INTO decision(transaction_id, itinerary_id, amount_minor) VALUES (?, ?, ?)",
                    (transaction_id, itinerary_id, amount_minor),
                )
                connection.execute(
                    "UPDATE itinerary SET spent_minor = spent_minor + ? WHERE id = ?",
                    (amount_minor, itinerary_id),
                )
                connection.commit()
                return Decision(True, "reserved")
            except Exception:
                connection.rollback()
                raise

    def close(self) -> None:
        self._connection.close()

