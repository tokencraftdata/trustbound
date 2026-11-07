"""Narrow signed budget-allocation authority.

This component establishes non-overlapping coordinator caps.  It is intentionally
not presented as the research contribution: budget locking is standard stateful
authorization.  The epoch-completeness result begins after these rights exist.
"""

from __future__ import annotations

import base64
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .epoch import public_key_from_text, public_key_text


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


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
        self._connection = sqlite3.connect(str(path))
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS trip (
              trip_id TEXT PRIMARY KEY,
              budget_minor INTEGER NOT NULL,
              currency TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS allocation (
              right_id TEXT PRIMARY KEY,
              trip_id TEXT NOT NULL,
              coordinator_id TEXT NOT NULL,
              generation INTEGER NOT NULL,
              cap_minor INTEGER NOT NULL,
              active INTEGER NOT NULL
            );
            """
        )
        self._connection.commit()
        self._key = Ed25519PrivateKey.generate()

    @property
    def public_key(self) -> str:
        return public_key_text(self._key.public_key())

    def create_trip(self, trip_id: str, budget_minor: int, currency: str) -> None:
        self._connection.execute(
            "INSERT INTO trip(trip_id, budget_minor, currency) VALUES (?, ?, ?)",
            (trip_id, budget_minor, currency),
        )
        self._connection.commit()

    def issue(
        self,
        trip_id: str,
        coordinator_id: str,
        cap_minor: int,
        ttl_seconds: int = 3_600,
    ) -> AllocationRight:
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            trip = connection.execute(
                "SELECT budget_minor, currency FROM trip WHERE trip_id = ?", (trip_id,)
            ).fetchone()
            if trip is None:
                raise KeyError(trip_id)
            allocated = connection.execute(
                "SELECT COALESCE(SUM(cap_minor), 0) FROM allocation WHERE trip_id = ? AND active = 1",
                (trip_id,),
            ).fetchone()[0]
            if int(allocated) + cap_minor > int(trip[0]):
                raise RuntimeError("trip_budget_overallocated")
            generation = connection.execute(
                "SELECT COALESCE(MAX(generation), 0) + 1 FROM allocation WHERE trip_id = ? AND coordinator_id = ?",
                (trip_id, coordinator_id),
            ).fetchone()[0]
            right_id = str(uuid.uuid4())
            issued_at = int(time.time())
            unsigned = {
                "trip_id": trip_id,
                "coordinator_id": coordinator_id,
                "generation": int(generation),
                "cap_minor": cap_minor,
                "currency": str(trip[1]),
                "right_id": right_id,
                "issued_at": issued_at,
                "expires_at": issued_at + ttl_seconds,
            }
            signature = _b64(self._key.sign(rfc8785.dumps(unsigned)))
            connection.execute(
                "INSERT INTO allocation VALUES (?, ?, ?, ?, ?, 1)",
                (right_id, trip_id, coordinator_id, generation, cap_minor),
            )
            connection.commit()
            return AllocationRight(**unsigned, signature=signature)
        except Exception:
            connection.rollback()
            raise

    def retire(self, right_id: str) -> None:
        cursor = self._connection.execute(
            "UPDATE allocation SET active = 0 WHERE right_id = ? AND active = 1",
            (right_id,),
        )
        if cursor.rowcount != 1:
            raise KeyError(right_id)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()


def verify_allocation(
    right: AllocationRight,
    authority_public_key: str,
    expected_coordinator: str,
    now: int | None = None,
) -> bool:
    if right.coordinator_id != expected_coordinator or right.cap_minor < 0:
        return False
    if (int(time.time()) if now is None else now) >= right.expires_at:
        return False
    try:
        public_key_from_text(authority_public_key).verify(
            _unb64(right.signature), rfc8785.dumps(right.unsigned_payload())
        )
        return True
    except Exception:
        return False
