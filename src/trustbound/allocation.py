"""Persistent allocation admission with explicit one-time claims.

A signature authenticates a token; it does not authorize use after retirement.
A trusted coordinator must claim its allocation before starting any work. Claimed
capacity remains reserved even after retirement or expiry, because work may be
in flight or funds already spent. This prototype does not settle that exposure.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import sqlite3
import time
import uuid

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .epoch import public_key_from_text, public_key_text

MAX_MINOR = 2**63 - 1
MAX_TTL = 2**31 - 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _valid_amount(value: int) -> bool:
    return type(value) is int and 0 <= value <= MAX_MINOR


@dataclass(frozen=True)
class AllocationRight:
    trip_id: str
    coordinator_id: str
    generation: int
    cap_minor: int
    currency: str
    right_id: str
    issued_at: int
    expires_at: int
    signature: str

    def unsigned_payload(self) -> dict:
        payload = asdict(self)
        payload.pop("signature")
        return payload


class AllocationAuthority:
    def __init__(self, path: str | Path) -> None:
        self._connection = sqlite3.connect(str(path), isolation_level=None, timeout=10)
        connection = self._connection
        try:
            connection.execute("PRAGMA synchronous=EXTRA")
            connection.execute("PRAGMA fullfsync=ON")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(allocation)")}
            if columns and not {"claimed", "issued_at", "expires_at"} <= columns:
                # An old database cannot tell us whether exported rights were used.
                raise RuntimeError("legacy_allocation_requires_migration")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS trip (
                  trip_id TEXT PRIMARY KEY, budget_minor INTEGER NOT NULL CHECK(budget_minor >= 0),
                  currency TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS allocation (
                  right_id TEXT PRIMARY KEY, trip_id TEXT NOT NULL,
                  coordinator_id TEXT NOT NULL, generation INTEGER NOT NULL,
                  cap_minor INTEGER NOT NULL CHECK(cap_minor >= 0),
                  active INTEGER NOT NULL CHECK(active IN (0, 1)),
                  claimed INTEGER NOT NULL DEFAULT 0 CHECK(claimed IN (0, 1)),
                  issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS allocation_signing_identity (
                  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                  private_key BLOB NOT NULL);
            """)
            with self._transaction():
                identity = connection.execute(
                    "SELECT private_key FROM allocation_signing_identity WHERE singleton=1"
                ).fetchone()
                if identity is None:
                    if connection.execute("SELECT COUNT(*) FROM allocation").fetchone()[0]:
                        raise RuntimeError("allocation_identity_requires_migration")
                    self._key = Ed25519PrivateKey.generate()
                    raw = self._key.private_bytes(
                        serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                        serialization.NoEncryption(),
                    )
                    connection.execute("INSERT INTO allocation_signing_identity VALUES (1, ?)", (raw,))
                else:
                    self._key = Ed25519PrivateKey.from_private_bytes(identity[0])
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def _transaction(self):
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self._connection.execute("COMMIT")
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise

    @property
    def public_key(self) -> str:
        return public_key_text(self._key.public_key())

    def create_trip(self, trip_id: str, budget_minor: int, currency: str) -> None:
        if (not _valid_amount(budget_minor) or type(trip_id) is not str or not trip_id
                or type(currency) is not str or not re.fullmatch(r"[A-Z]{3}", currency)):
            raise ValueError("invalid_trip")
        with self._transaction():
            self._connection.execute(
                "INSERT INTO trip(trip_id, budget_minor, currency) VALUES (?, ?, ?)",
                (trip_id, budget_minor, currency),
            )

    def issue(
        self, trip_id: str, coordinator_id: str, cap_minor: int, ttl_seconds: int = 3_600,
    ) -> AllocationRight:
        if not _valid_amount(cap_minor):
            raise ValueError("invalid_allocation_cap")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= MAX_TTL:
            raise ValueError("invalid_allocation_lifetime")
        if type(coordinator_id) is not str or not coordinator_id:
            raise ValueError("invalid_coordinator")
        connection = self._connection
        with self._transaction():
            trip = connection.execute(
                "SELECT budget_minor, currency FROM trip WHERE trip_id=?", (trip_id,)
            ).fetchone()
            if trip is None:
                raise KeyError(trip_id)
            # Retirement only releases a right that never crossed the claim boundary.
            # Expiry does not imply that already claimed work has been discharged.
            allocated = connection.execute(
                "SELECT COALESCE(SUM(cap_minor), 0) FROM allocation "
                "WHERE trip_id=? AND (active=1 OR claimed=1)", (trip_id,),
            ).fetchone()[0]
            if allocated + cap_minor > trip[0]:
                raise RuntimeError("trip_budget_overallocated")
            generation = connection.execute(
                "SELECT COALESCE(MAX(generation), 0) + 1 FROM allocation "
                "WHERE trip_id=? AND coordinator_id=?", (trip_id, coordinator_id),
            ).fetchone()[0]
            issued_at = int(time.time())
            unsigned = {
                "trip_id": trip_id, "coordinator_id": coordinator_id, "generation": generation,
                "cap_minor": cap_minor, "currency": trip[1], "right_id": str(uuid.uuid4()),
                "issued_at": issued_at, "expires_at": issued_at + ttl_seconds,
            }
            signature = _b64(self._key.sign(rfc8785.dumps(unsigned)))
            connection.execute(
                "INSERT INTO allocation "
                "(right_id,trip_id,coordinator_id,generation,cap_minor,active,claimed,issued_at,expires_at) "
                "VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?)",
                (unsigned["right_id"], trip_id, coordinator_id, generation, cap_minor,
                 issued_at, unsigned["expires_at"]),
            )
            return AllocationRight(**unsigned, signature=signature)

    def is_available(self, right: AllocationRight, expected_coordinator: str,
                     now: int | None = None) -> bool:
        """Read current availability. Call claim, not this advisory read, before work."""
        if not verify_allocation_signature(right, self.public_key, expected_coordinator, now):
            return False
        row = self._connection.execute(
            "SELECT a.trip_id,a.coordinator_id,a.generation,a.cap_minor,t.currency,"
            "a.issued_at,a.expires_at,a.active,a.claimed FROM allocation a "
            "JOIN trip t ON t.trip_id=a.trip_id WHERE a.right_id=?", (right.right_id,),
        ).fetchone()
        return row == (right.trip_id, right.coordinator_id, right.generation, right.cap_minor,
                       right.currency, right.issued_at, right.expires_at, 1, 0)

    def claim(self, right: AllocationRight, expected_coordinator: str) -> AllocationRight:
        """Atomically admit one trusted coordinator; a lost reply stays claimed."""
        with self._transaction():
            if not self.is_available(right, expected_coordinator):
                raise RuntimeError("allocation_not_available")
            self._connection.execute("UPDATE allocation SET claimed=1 WHERE right_id=?", (right.right_id,))
        return right

    def retire(self, right_id: str) -> None:
        """Block future claims; retain all capacity already claimed by a coordinator."""
        with self._transaction():
            cursor = self._connection.execute(
                "UPDATE allocation SET active=0 WHERE right_id=? AND active=1", (right_id,),
            )
            if cursor.rowcount != 1:
                raise KeyError(right_id)

    def close(self) -> None:
        self._connection.close()


def verify_allocation_signature(
    right: AllocationRight, authority_public_key: str, expected_coordinator: str,
    now: int | None = None,
) -> bool:
    """Offline authenticity/time check only; it says nothing about retirement or use."""
    try:
        current = int(time.time()) if now is None else now
        if (right.coordinator_id != expected_coordinator or not _valid_amount(right.cap_minor)
                or type(right.generation) is not int or right.generation < 1
                or type(right.issued_at) is not int or type(right.expires_at) is not int
                or type(current) is not int
                or not 0 <= right.issued_at <= current < right.expires_at
                or not 1 <= right.expires_at - right.issued_at <= MAX_TTL):
            return False
        public_key_from_text(authority_public_key).verify(
            _unb64(right.signature), rfc8785.dumps(right.unsigned_payload())
        )
        return True
    except Exception:
        return False


def verify_allocation(
    right: AllocationRight, authority_public_key: str, expected_coordinator: str,
    now: int | None = None, *, authority: AllocationAuthority | None = None,
) -> bool:
    """Check current availability against a trusted authority; fail closed offline.

    This is advisory: only the atomic claim authorizes starting work. Callers must
    not treat a successful read or an offline signature as a reusable capability.
    """
    if authority is None or authority.public_key != authority_public_key:
        return False
    return authority.is_available(right, expected_coordinator, now)
