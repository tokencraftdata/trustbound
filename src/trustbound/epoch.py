"""Payment-epoch admission, reconciliation, and verifiable closure.

RESEARCH PROTOTYPE. Not a refinement of formal/Closure.lean. Do not deploy.
Local transition checks cannot establish an external processor's completeness.

The model deliberately separates three roles:

* a processor observes economic effects and owns an admission fence;
* a witness authenticates append-only processor checkpoints but does not observe
  economic effects;
* an auditor validates a vector of processor closures.

Witness signatures therefore prevent equivocation only.  They cannot repair an
observer that omits an effect it alone could see.
"""

from __future__ import annotations

import base64
import hashlib
import sqlite3
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

import rfc8785
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


PaymentStatus = Literal["confirmed", "released", "uncertain"]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def public_key_text(key: Ed25519PublicKey) -> str:
    return _b64(
        key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


def public_key_from_text(value: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(_unb64(value))


@dataclass(frozen=True)
class ReconciledPayment:
    sequence: int
    payment_id: str
    coordinator_id: str
    amount_minor: int
    quote_version: int
    status: PaymentStatus
    effect_reference: str | None

    @property
    def liability_minor(self) -> int:
        return 0 if self.status == "released" else self.amount_minor


@dataclass(frozen=True)
class ClosureStatement:
    processor_id: str
    epoch_id: str
    high_watermark: int
    previous_root: str | None
    entries: tuple[ReconciledPayment, ...]
    root: str
    processor_signature: str

    def unsigned_payload(self) -> dict:
        return {
            "processor_id": self.processor_id,
            "epoch_id": self.epoch_id,
            "high_watermark": self.high_watermark,
            "previous_root": self.previous_root,
            "entries": [asdict(entry) for entry in self.entries],
            "root": self.root,
        }


@dataclass(frozen=True)
class WitnessAttestation:
    witness_id: str
    processor_id: str
    epoch_id: str
    root: str
    signature: str


@dataclass(frozen=True)
class ProcessorClosure:
    statement: ClosureStatement
    attestations: tuple[WitnessAttestation, ...]


@dataclass(frozen=True)
class AuditDecision:
    valid: bool
    reason: str
    liability_minor: int = 0


def _entries_root(
    processor_id: str,
    epoch_id: str,
    previous_root: str | None,
    entries: Iterable[ReconciledPayment],
) -> str:
    payload = {
        "processor_id": processor_id,
        "epoch_id": epoch_id,
        "previous_root": previous_root,
        "entries": [asdict(entry) for entry in entries],
    }
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


class FencedProcessor:
    """A processor-local, persistent admission fence and reconciliation log."""

    def __init__(self, processor_id: str, path: str | Path) -> None:
        self.processor_id = processor_id
        self.path = str(path)
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS epoch (
              epoch_id TEXT PRIMARY KEY,
              state TEXT NOT NULL,
              previous_root TEXT
            );
            CREATE TABLE IF NOT EXISTS payment (
              epoch_id TEXT NOT NULL,
              sequence INTEGER NOT NULL,
              payment_id TEXT NOT NULL UNIQUE,
              coordinator_id TEXT NOT NULL,
              amount_minor INTEGER NOT NULL,
              quote_version INTEGER NOT NULL,
              status TEXT,
              effect_reference TEXT,
              PRIMARY KEY(epoch_id, sequence)
            );
            """
        )
        self._connection.commit()
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS signing_identity (
                 singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                 processor_id TEXT NOT NULL, private_key BLOB NOT NULL)"""
        )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            identity = self._connection.execute(
                "SELECT processor_id, private_key FROM signing_identity WHERE singleton = 1"
            ).fetchone()
            if identity is None:
                if self._connection.execute("SELECT COUNT(*) FROM epoch").fetchone()[0]:
                    raise RuntimeError("legacy_processor_identity_requires_migration")
                key = Ed25519PrivateKey.generate()
                raw = key.private_bytes(
                    serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                    serialization.NoEncryption(),
                )
                self._connection.execute(
                    "INSERT INTO signing_identity VALUES (1, ?, ?)", (processor_id, raw)
                )
                self._key = key
            else:
                if identity[0] != processor_id:
                    raise RuntimeError("processor_identity_mismatch")
                self._key = Ed25519PrivateKey.from_private_bytes(identity[1])
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            self._connection.close()
            raise

    @property
    def public_key(self) -> str:
        return public_key_text(self._key.public_key())

    def open_epoch(self, epoch_id: str, previous_root: str | None = None) -> None:
        with self._lock:
            self._connection.execute(
                "INSERT INTO epoch(epoch_id, state, previous_root) VALUES (?, 'open', ?)",
                (epoch_id, previous_root),
            )
            self._connection.commit()

    def admit(
        self,
        epoch_id: str,
        payment_id: str,
        coordinator_id: str,
        amount_minor: int,
        quote_version: int,
    ) -> int:
        """Admit before execution; no admission is possible after the fence closes."""
        if (type(amount_minor) is not int or amount_minor < 0
                or type(quote_version) is not int or quote_version < 1
                or not all((epoch_id, payment_id, coordinator_id))):
            raise ValueError("invalid payment admission")
        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    """SELECT sequence, epoch_id, coordinator_id, amount_minor, quote_version
                       FROM payment WHERE payment_id = ?""", (payment_id,)
                ).fetchone()
                if prior is not None:
                    if prior[1:] != (epoch_id, coordinator_id, amount_minor, quote_version):
                        raise RuntimeError("payment_id_conflict")
                    connection.commit()
                    return int(prior[0])
                epoch = connection.execute(
                    "SELECT state FROM epoch WHERE epoch_id = ?", (epoch_id,)
                ).fetchone()
                if epoch is None or epoch[0] != "open":
                    raise RuntimeError("epoch_closed_or_unknown")
                row = connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM payment WHERE epoch_id = ?",
                    (epoch_id,),
                ).fetchone()
                sequence = int(row[0])
                connection.execute(
                    """INSERT INTO payment(
                           epoch_id, sequence, payment_id, coordinator_id,
                           amount_minor, quote_version
                       ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        epoch_id,
                        sequence,
                        payment_id,
                        coordinator_id,
                        amount_minor,
                        quote_version,
                    ),
                )
                connection.commit()
                return sequence
            except Exception:
                connection.rollback()
                raise

    def reconcile(
        self,
        payment_id: str,
        status: PaymentStatus,
        effect_reference: str | None,
    ) -> None:
        """Record a trusted simulator outcome, not an authenticated API receipt.

        'released' asserts that further execution is impossible. A timeout,
        absent webhook or transient failure is only 'uncertain'. An external
        adapter must establish terminal no-effect before invoking release.
        """
        if status not in {"confirmed", "released", "uncertain"}:
            raise ValueError(status)
        if status == "confirmed" and not effect_reference:
            raise ValueError("confirmed effects require a processor reference")
        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                prior = connection.execute(
                    "SELECT status, effect_reference FROM payment WHERE payment_id = ?",
                    (payment_id,),
                ).fetchone()
                if prior is None:
                    raise KeyError(payment_id)
                if prior[0] in {"confirmed", "released"} and prior != (status, effect_reference):
                    raise RuntimeError("terminal_payment_conflict")
                connection.execute(
                    "UPDATE payment SET status = ?, effect_reference = ? WHERE payment_id = ?",
                    (status, effect_reference, payment_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def close_epoch(self, epoch_id: str) -> ClosureStatement:
        """Close atomically and account for every admitted sequence.

        Missing processor visibility is represented as ``uncertain`` and retains
        the full liability.  It is never silently treated as released.
        """
        with self._lock:
            connection = self._connection
            connection.execute("BEGIN IMMEDIATE")
            try:
                epoch_row = connection.execute(
                    "SELECT state, previous_root FROM epoch WHERE epoch_id = ?",
                    (epoch_id,),
                ).fetchone()
                if epoch_row is None or epoch_row[0] != "open":
                    raise RuntimeError("epoch_closed_or_unknown")
                connection.execute(
                    "UPDATE payment SET status = 'uncertain' WHERE epoch_id = ? AND status IS NULL",
                    (epoch_id,),
                )
                connection.execute(
                    "UPDATE epoch SET state = 'closed' WHERE epoch_id = ?", (epoch_id,)
                )
                rows = connection.execute(
                    """SELECT sequence, payment_id, coordinator_id, amount_minor,
                              quote_version, status, effect_reference
                       FROM payment WHERE epoch_id = ? ORDER BY sequence""",
                    (epoch_id,),
                ).fetchall()
                entries = tuple(ReconciledPayment(*row) for row in rows)
                previous_root = epoch_row[1]
                root = _entries_root(self.processor_id, epoch_id, previous_root, entries)
                payload = {
                    "processor_id": self.processor_id,
                    "epoch_id": epoch_id,
                    "high_watermark": len(entries),
                    "previous_root": previous_root,
                    "entries": [asdict(entry) for entry in entries],
                    "root": root,
                }
                signature = _b64(self._key.sign(rfc8785.dumps(payload)))
                connection.commit()
                return ClosureStatement(
                    processor_id=self.processor_id,
                    epoch_id=epoch_id,
                    high_watermark=len(entries),
                    previous_root=previous_root,
                    entries=entries,
                    root=root,
                    processor_signature=signature,
                )
            except Exception:
                connection.rollback()
                raise

    def close(self) -> None:
        self._connection.close()


def verify_statement(statement: ClosureStatement, processor_key: str) -> AuditDecision:
    sequences = [entry.sequence for entry in statement.entries]
    expected = list(range(1, statement.high_watermark + 1))
    if sequences != expected:
        return AuditDecision(False, "sequence_gap")
    if any(entry.status not in {"confirmed", "released", "uncertain"} for entry in statement.entries):
        return AuditDecision(False, "unaccounted_admission")
    root = _entries_root(
        statement.processor_id,
        statement.epoch_id,
        statement.previous_root,
        statement.entries,
    )
    if root != statement.root:
        return AuditDecision(False, "root_mismatch")
    try:
        public_key_from_text(processor_key).verify(
            _unb64(statement.processor_signature),
            rfc8785.dumps(statement.unsigned_payload()),
        )
    except Exception:
        return AuditDecision(False, "processor_signature")
    liability = sum(entry.liability_minor for entry in statement.entries)
    return AuditDecision(True, "verified", liability)


class LogWitness:
    """Persistent non-equivocation witness; explicitly not a payment observer."""

    def __init__(self, witness_id: str, path: str | Path) -> None:
        self.witness_id = witness_id
        self._connection = sqlite3.connect(str(path))
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS checkpoint (
                   processor_id TEXT NOT NULL,
                   epoch_id TEXT NOT NULL,
                   root TEXT NOT NULL,
                   PRIMARY KEY(processor_id, epoch_id)
               )"""
        )
        self._connection.commit()
        self._key = Ed25519PrivateKey.generate()

    @property
    def public_key(self) -> str:
        return public_key_text(self._key.public_key())

    def attest(self, statement: ClosureStatement, processor_key: str) -> WitnessAttestation:
        verified = verify_statement(statement, processor_key)
        if not verified.valid:
            raise ValueError(verified.reason)
        existing = self._connection.execute(
            "SELECT root FROM checkpoint WHERE processor_id = ? AND epoch_id = ?",
            (statement.processor_id, statement.epoch_id),
        ).fetchone()
        if existing is not None and existing[0] != statement.root:
            raise RuntimeError("equivocation")
        self._connection.execute(
            "INSERT OR IGNORE INTO checkpoint(processor_id, epoch_id, root) VALUES (?, ?, ?)",
            (statement.processor_id, statement.epoch_id, statement.root),
        )
        self._connection.commit()
        payload = {
            "witness_id": self.witness_id,
            "processor_id": statement.processor_id,
            "epoch_id": statement.epoch_id,
            "root": statement.root,
        }
        return WitnessAttestation(
            witness_id=self.witness_id,
            processor_id=statement.processor_id,
            epoch_id=statement.epoch_id,
            root=statement.root,
            signature=_b64(self._key.sign(rfc8785.dumps(payload))),
        )

    def close(self) -> None:
        self._connection.close()


def audit_epoch_vector(
    closures: Iterable[ProcessorClosure],
    required_processors: set[str],
    processor_keys: dict[str, str],
    witness_keys: dict[str, str],
    witness_threshold: int,
    budget_minor: int,
) -> AuditDecision:
    closures = tuple(closures)
    if {item.statement.processor_id for item in closures} != required_processors:
        return AuditDecision(False, "processor_set_incomplete")
    epoch_ids = {item.statement.epoch_id for item in closures}
    if len(epoch_ids) != 1:
        return AuditDecision(False, "epoch_mismatch")
    total_liability = 0
    for closure in closures:
        statement = closure.statement
        key = processor_keys.get(statement.processor_id)
        if key is None:
            return AuditDecision(False, "unknown_processor")
        verified = verify_statement(statement, key)
        if not verified.valid:
            return verified
        valid_witnesses: set[str] = set()
        for attestation in closure.attestations:
            if (
                attestation.processor_id != statement.processor_id
                or attestation.epoch_id != statement.epoch_id
                or attestation.root != statement.root
            ):
                continue
            witness_key = witness_keys.get(attestation.witness_id)
            if witness_key is None:
                continue
            payload = {
                "witness_id": attestation.witness_id,
                "processor_id": attestation.processor_id,
                "epoch_id": attestation.epoch_id,
                "root": attestation.root,
            }
            try:
                public_key_from_text(witness_key).verify(
                    _unb64(attestation.signature), rfc8785.dumps(payload)
                )
                valid_witnesses.add(attestation.witness_id)
            except Exception:
                pass
        if len(valid_witnesses) < witness_threshold:
            return AuditDecision(False, "witness_threshold")
        total_liability += verified.liability_minor
    if total_liability > budget_minor:
        return AuditDecision(False, "budget_exceeded", total_liability)
    return AuditDecision(True, "complete_for_fenced_scope", total_liability)


def indistinguishable_unfenced_runs() -> tuple[dict, dict]:
    """Return equal evidence for a clean run and one hidden off-fence charge.

    This is the executable counterexample behind the impossibility statement:
    if an in-scope effect can bypass every accepted observer, no evidence-only
    auditor can distinguish the two runs.
    """
    evidence = {"epoch": "e1", "processor_roots": ["same-root"], "liability": 100}
    clean = {"evidence": evidence, "ground_truth_effects": [100]}
    attacked = {"evidence": evidence, "ground_truth_effects": [100, 75]}
    return clean, attacked
