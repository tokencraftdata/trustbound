"""Independent flight/hotel coordinators with persistent quote state."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from .epoch import FencedProcessor


QuoteState = Literal["reserved", "released", "uncertain", "confirmed", "revoked"]


class PersistentCoordinator:
    """A leg-specific coordinator; instances never share a database."""

    def __init__(
        self,
        coordinator_id: str,
        allocation_minor: int,
        path: str | Path,
    ) -> None:
        if type(allocation_minor) is not int or allocation_minor < 0 or not coordinator_id:
            raise ValueError("invalid_coordinator_allocation")
        self.coordinator_id = coordinator_id
        self.allocation_minor = allocation_minor
        self.path = str(path)
        self._connection = sqlite3.connect(self.path)
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS control (
              singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
              revoked INTEGER NOT NULL DEFAULT 0
            );
            INSERT OR IGNORE INTO control(singleton, revoked) VALUES (1, 0);
            CREATE TABLE IF NOT EXISTS quote (
              quote_id TEXT NOT NULL,
              version INTEGER NOT NULL,
              amount_minor INTEGER NOT NULL,
              state TEXT NOT NULL,
              payment_id TEXT,
              PRIMARY KEY(quote_id, version)
            );
            """
        )
        self._connection.commit()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            columns = {row[1] for row in self._connection.execute("PRAGMA table_info(quote)")}
            if "processor_key" not in columns:
                if self._connection.execute("SELECT COUNT(*) FROM quote").fetchone()[0]:
                    raise RuntimeError("legacy_coordinator_requires_migration")
                for column in ("processor_id", "processor_key", "epoch_id"):
                    self._connection.execute(f"ALTER TABLE quote ADD COLUMN {column} TEXT")
            self._connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS quote_payment_id ON quote(payment_id)"
            )
            self._connection.execute(
                """CREATE TABLE IF NOT EXISTS coordinator_identity (
                   singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                   coordinator_id TEXT NOT NULL, allocation_minor INTEGER NOT NULL)"""
            )
            self._connection.execute(
                "INSERT OR IGNORE INTO coordinator_identity VALUES (1, ?, ?)",
                (coordinator_id, allocation_minor),
            )
            identity = self._connection.execute(
                "SELECT coordinator_id, allocation_minor FROM coordinator_identity"
            ).fetchone()
            if identity != (coordinator_id, allocation_minor):
                raise RuntimeError("coordinator_identity_or_allocation_mismatch")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            self._connection.close()
            raise

    def _liability(self) -> int:
        row = self._connection.execute(
            """SELECT COALESCE(SUM(amount_minor), 0) FROM quote
               WHERE state IN ('reserved', 'uncertain', 'confirmed')"""
        ).fetchone()
        return int(row[0])

    def reserve_quote(self, quote_id: str, version: int, amount_minor: int) -> None:
        if (not quote_id or type(version) is not int or version < 1
                or type(amount_minor) is not int or amount_minor < 0):
            raise ValueError("invalid_quote")
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            revoked = connection.execute(
                "SELECT revoked FROM control WHERE singleton = 1"
            ).fetchone()[0]
            if revoked:
                raise RuntimeError("authorization_revoked")
            prior = connection.execute(
                "SELECT amount_minor, state, version FROM quote WHERE quote_id = ? ORDER BY version DESC LIMIT 1",
                (quote_id,),
            ).fetchone()
            if prior and version <= prior[2]:
                raise RuntimeError("quote_version_not_increasing")
            liability = self._liability()
            if prior and prior[1] == "reserved":
                liability -= int(prior[0])
            if liability + amount_minor > self.allocation_minor:
                raise RuntimeError("allocation_exceeded")
            if prior and prior[1] == "reserved":
                connection.execute(
                    "UPDATE quote SET state = 'released' WHERE quote_id = ? AND state = 'reserved'",
                    (quote_id,),
                )
            connection.execute(
                "INSERT INTO quote(quote_id, version, amount_minor, state) VALUES (?, ?, ?, 'reserved')",
                (quote_id, version, amount_minor),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def submit(
        self,
        processor: FencedProcessor,
        epoch_id: str,
        quote_id: str,
        version: int,
        payment_id: str,
    ) -> int:
        """Durably claim before dispatch. Failed dispatch retains liability.

        A retry can only replay the same payment, epoch and processor identity.
        The processor must provide durable idempotent admission, as the local
        FencedProcessor does; this is not an arbitrary PSP adapter interface.
        """
        if not payment_id or not epoch_id:
            raise ValueError("invalid_submission")
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            if connection.execute("SELECT revoked FROM control").fetchone()[0]:
                raise RuntimeError("authorization_revoked")
            row = connection.execute(
                """SELECT amount_minor, state, payment_id, processor_id, processor_key, epoch_id
                   FROM quote WHERE quote_id = ? AND version = ?""", (quote_id, version)
            ).fetchone()
            if row is None:
                raise RuntimeError("quote_not_reservable")
            binding = (payment_id, processor.processor_id, processor.public_key, epoch_id)
            if row[2] is not None:
                if row[2:] != binding:
                    raise RuntimeError("submission_conflict")
                if row[1] != "uncertain":
                    raise RuntimeError("quote_already_terminal")
            else:
                if row[1] != "reserved":
                    raise RuntimeError("quote_not_reservable")
                connection.execute(
                    """UPDATE quote SET state = 'uncertain', payment_id = ?, processor_id = ?,
                       processor_key = ?, epoch_id = ? WHERE quote_id = ? AND version = ?""",
                    (*binding, quote_id, version),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return processor.admit(
            epoch_id, payment_id, self.coordinator_id, int(row[0]), version
        )

    def apply_receipt(self, payment_id: str, status: QuoteState) -> None:
        """Trusted local receipt input; network authenticity is not implemented."""
        if status not in {"released", "uncertain", "confirmed"}:
            raise ValueError(status)
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            prior = connection.execute(
                "SELECT state FROM quote WHERE payment_id = ?", (payment_id,)
            ).fetchone()
            if prior is None:
                raise KeyError(payment_id)
            if prior[0] in {"confirmed", "released"} and prior[0] != status:
                raise RuntimeError("terminal_receipt_conflict")
            connection.execute(
                "UPDATE quote SET state = ? WHERE payment_id = ?", (status, payment_id)
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def revoke(self) -> None:
        """Fence new local claims, not dispatch already claimed before revocation."""
        self._connection.execute("UPDATE control SET revoked = 1 WHERE singleton = 1")
        self._connection.execute(
            "UPDATE quote SET state = 'revoked' WHERE state = 'reserved' AND payment_id IS NULL"
        )
        self._connection.commit()

    def snapshot(self) -> dict:
        return {
            "coordinator_id": self.coordinator_id,
            "allocation_minor": self.allocation_minor,
            "liability_minor": self._liability(),
            "quotes": self._connection.execute(
                "SELECT quote_id, version, amount_minor, state, payment_id FROM quote ORDER BY quote_id, version"
            ).fetchall(),
        }

    def close(self) -> None:
        self._connection.close()
