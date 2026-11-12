"""Narrow durable dispatch gate for one Stripe test epoch; not a verified deployment.

The transport/credential boundary must enforce this gate. A process holding the
same Stripe key can bypass it. SQLite durability assumes honest stable storage.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast


PaymentObservation = Mapping[str, Any]
PaymentState = tuple[str, int, int]
_T = TypeVar("_T")


class PaymentTransport(Protocol):
    """Trusted transport used for a single dispatch invocation."""

    def request(
        self, method: str, path: str, body: dict[str, str], idem: str
    ) -> tuple[int, dict[str, Any]]: ...


def _validate_registration(row: PaymentObservation) -> None:
    """Require an inert intent in the explicitly supported test configuration."""
    if (
        row.get("object") != "payment_intent"
        or row.get("livemode") is not False
        or not re.fullmatch(r"pi_[A-Za-z0-9]+", row.get("id", ""))
        or row.get("confirmation_method") != "manual"
        or row.get("capture_method") != "manual"
        or row.get("payment_method_types") != ["card"]
        or row.get("status") != "requires_payment_method"
        or row.get("payment_method") is not None
        or row.get("customer") is not None
        or row.get("currency") != "usd"
        or type(row.get("amount")) is not int
        or not 50 <= row["amount"] <= 500
        or row.get("amount_received") != 0
        or row.get("amount_capturable") != 0
    ):
        raise ValueError("not_inert_constrained_intent")


def _observation_matches_scope(row: PaymentObservation, amount: int) -> bool:
    """Check provider configuration and amount bounds before reading an outcome."""
    return not (
        row.get("object") != "payment_intent"
        or row.get("livemode") is not False
        or row.get("currency") != "usd"
        or row.get("amount") != amount
        or row.get("confirmation_method") != "manual"
        or row.get("capture_method") != "manual"
        or row.get("payment_method_types") != ["card"]
        or type(row.get("amount_received")) is not int
        or type(row.get("amount_capturable")) is not int
        or not 0 <= row["amount_received"] <= amount
        or not 0 <= row["amount_capturable"] <= amount
    )


def _observation_state(row: PaymentObservation, amount: int) -> PaymentState:
    """Classify a scope-checked observation without inferring provider truth."""
    received = row["amount_received"]
    capturable = row["amount_capturable"]
    status = "uncertain"
    if row.get("status") == "canceled" and capturable == 0 and received == 0:
        status = "canceled"
    if row.get("status") == "succeeded" and capturable == 0 and received == amount:
        status = "succeeded"
    return status, received, capturable


def _retained_amount(record: Mapping[str, Any], conflicted: set[str]) -> int:
    # A known conflict restores the configured reservation. It is not a monetary
    # bound for an out-of-contract provider.
    if record["status"] == "uncertain" or record["id"] in conflicted:
        return record["amount"]
    return record["received"]


class StripeGate:
    def __init__(self, path: str | Path, epoch: str) -> None:
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=EXTRA")
        self.db.execute("PRAGMA fullfsync=ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS epoch(id TEXT PRIMARY KEY, closed INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS payment(id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
              status TEXT NOT NULL, received INTEGER NOT NULL, capturable INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS command(id INTEGER PRIMARY KEY, payment_id TEXT NOT NULL,
              action TEXT NOT NULL, claimed INTEGER NOT NULL DEFAULT 0,
              UNIQUE(payment_id, action));
            CREATE TABLE IF NOT EXISTS observation_conflict(payment_id TEXT NOT NULL,
              reason TEXT NOT NULL, PRIMARY KEY(payment_id, reason));
            """
        )

        def initialize() -> None:
            rows = self.db.execute("SELECT id FROM epoch").fetchall()
            if rows and rows != [(epoch,)]:
                raise ValueError("epoch_identity_mismatch")
            self.db.execute("INSERT OR IGNORE INTO epoch VALUES (?, 0)", (epoch,))

        try:
            self._transaction(initialize)
        except BaseException:
            self.db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def _transaction(self, operation: Callable[[], _T]) -> _T:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = operation()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _open(self) -> None:
        if self.db.execute("SELECT closed FROM epoch").fetchone()[0]:
            raise RuntimeError("epoch_fenced")

    def _capture_claimed(self, payment_id: str) -> bool:
        # Necessary provenance only. A durable claim does not prove that the
        # transport ran, the provider executed, or the observation is truthful.
        row = self.db.execute(
            "SELECT 1 FROM command WHERE payment_id=? AND action='capture' AND claimed=1",
            (payment_id,),
        ).fetchone()
        return row is not None

    def _conflict(self, payment_id: str, reason: str) -> None:
        # Called inside the same transaction as observation/snapshot validation.
        # Keep only the identity and fixed reason, never raw provider responses.
        self.db.execute(
            "INSERT OR IGNORE INTO observation_conflict VALUES (?, ?)",
            (payment_id, reason),
        )

    def _unconflicted(self, payment_id: str) -> None:
        row = self.db.execute(
            "SELECT 1 FROM observation_conflict WHERE payment_id=?", (payment_id,)
        ).fetchone()
        if row is not None:
            raise RuntimeError("payment_contract_conflict")

    def register(self, row: PaymentObservation) -> None:
        """Journal an inert payment before any authority can be granted."""
        # Whitelist configuration: no permissive default on absent evidence.
        _validate_registration(row)

        def operation() -> None:
            self._open()
            self.db.execute(
                "INSERT INTO payment VALUES (?, ?, 'uncertain', 0, 0)",
                (row["id"], row["amount"]),
            )

        self._transaction(operation)

    def grant(self, payment_id: str, action: str) -> int:
        """Persist a command for a registered, unresolved payment before fencing."""
        if action not in {"confirm", "capture"}:
            raise ValueError("unsupported_action")

        def operation() -> int:
            self._open()
            self._unconflicted(payment_id)
            row = self.db.execute(
                "SELECT status FROM payment WHERE id=?", (payment_id,)
            ).fetchone()
            if row != ("uncertain",):
                raise RuntimeError("unknown_or_terminal_payment")
            cursor = self.db.execute(
                "INSERT INTO command(payment_id,action) VALUES (?, ?)",
                (payment_id, action),
            )
            # A successful INSERT into this INTEGER PRIMARY KEY table assigns an ID.
            return cast(int, cursor.lastrowid)

        return self._transaction(operation)

    def claim(self, command_id: int) -> tuple[str, str]:
        # An already granted request may execute after the fence. Crash after
        # claim is uncertain; no automatic redispatch. Resolve the known object.
        def operation() -> tuple[str, str]:
            row = self.db.execute(
                "SELECT payment_id,action,claimed FROM command WHERE id=?",
                (command_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("command_unknown_or_already_claimed")
            payment_id, action, claimed = row
            if claimed:
                raise RuntimeError("command_unknown_or_already_claimed")
            self._unconflicted(payment_id)
            self.db.execute("UPDATE command SET claimed=1 WHERE id=?", (command_id,))
            return payment_id, action

        return self._transaction(operation)

    def fence(self) -> None:
        """Stop new registrations and grants; existing commands may still execute."""
        self._transaction(lambda: self.db.execute("UPDATE epoch SET closed=1"))

    def dispatch(
        self, command_id: int, transport: PaymentTransport
    ) -> dict[str, Any]:
        """Trusted-worker entry point: one claim, one fixed transport invocation.

        `transport` is trusted and must not retry or expose credentials to agents.
        A timeout/exception/worker death leaves the committed claim in place.
        This is an invocation guarantee, not exactly-once provider execution.
        Python object privacy and this method are not process isolation.
        """
        payment_id, action = self.claim(command_id)
        epoch = self.db.execute("SELECT id FROM epoch").fetchone()[0]
        # This adapter is deliberately limited to synthetic Stripe test methods.
        body = {"payment_method": "pm_card_visa"} if action == "confirm" else {}
        code, _ = transport.request(
            "POST",
            f"/v1/payment_intents/{payment_id}/{action}",
            body,
            f"{epoch}:dispatch:{command_id}",
        )
        # Do not trust a POST reply as a closure observation or expose raw secrets.
        return {
            "payment_id": payment_id,
            "action": action,
            "http_status": code,
            "requires_authoritative_reconciliation": True,
        }

    def observe(self, row: PaymentObservation) -> None:
        # Caller supplies a fresh authenticated retrieval. This function does
        # not prove that retrieval occurred or that the provider is truthful.
        # Validation conflicts are committed BEFORE raising; raising inside the
        # transaction would roll back the very evidence that blocks resolution.
        def operation() -> Exception | None:
            prior = self.db.execute(
                "SELECT amount,status,received,capturable FROM payment WHERE id=?",
                (row.get("id"),),
            ).fetchone()
            if prior is None:
                raise ValueError("unknown_payment")
            amount, previous_status, previous_received, previous_capturable = prior
            previous_state = (previous_status, previous_received, previous_capturable)
            if not _observation_matches_scope(row, amount):
                self._conflict(row["id"], "observation_scope_mismatch")
                return ValueError("observation_scope_mismatch")
            state = _observation_state(row, amount)
            if previous_status != "uncertain" and state != previous_state:
                self._conflict(row["id"], "terminal_observation_changed")
                return RuntimeError("terminal_observation_changed")
            if row["amount_received"] > 0 and not self._capture_claimed(row["id"]):
                self._conflict(row["id"], "paid_without_claimed_capture")
                return RuntimeError("paid_without_claimed_capture")
            self.db.execute(
                "UPDATE payment SET status=?,received=?,capturable=? WHERE id=?",
                (*state, row["id"]),
            )
            return None

        error = self._transaction(operation)
        if error is not None:
            raise error

    def snapshot(self) -> dict[str, Any]:
        """Read one consistent view, persisting any missing-provenance conflicts."""

        def operation() -> dict[str, Any]:
            closed = bool(self.db.execute("SELECT closed FROM epoch").fetchone()[0])
            records = [
                dict(zip(("id", "amount", "status", "received", "capturable"), row))
                for row in self.db.execute(
                    "SELECT id,amount,status,received,capturable FROM payment ORDER BY id"
                )
            ]
            # Recheck historical rows too: opening an older database must not
            # preserve a resolved paid observation lacking capture provenance.
            for record in records:
                has_paid_outcome = record["received"] > 0 or record["status"] == "succeeded"
                if has_paid_outcome and not self._capture_claimed(record["id"]):
                    self._conflict(record["id"], "paid_without_claimed_capture")
            conflicts = [
                dict(zip(("payment_id", "reason"), row))
                for row in self.db.execute(
                    "SELECT payment_id,reason FROM observation_conflict ORDER BY payment_id,reason"
                )
            ]
            conflicted = {row["payment_id"] for row in conflicts}
            commands = [
                dict(zip(("id", "payment_id", "action", "claimed"), row))
                for row in self.db.execute(
                    "SELECT id,payment_id,action,claimed FROM command ORDER BY id"
                )
            ]
            resolved = not conflicts and all(
                record["status"] in {"canceled", "succeeded"} for record in records
            )
            return {
                "closed": closed,
                "records": records,
                "commands": commands,
                "contract_conflicts": conflicts,
                "has_contract_conflicts": bool(conflicts),
                "known_manifest_resolved": closed and resolved,
                "deployment_completeness_proved": False,
                "retained_minor": sum(
                    _retained_amount(record, conflicted) for record in records
                ),
            }

        return self._transaction(operation)
