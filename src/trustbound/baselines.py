"""Comparable authorization configurations.

The parity baseline intentionally receives the same itinerary facts and atomic
state as TrustBound. This prevents a straw-man comparison.
"""

from __future__ import annotations

from .ledger import AtomicLedger
from .models import Decision, ItineraryManifest
from .policy import evidence_commitment, itinerary_violations
from .protocol import ProtocolArtifacts, ProtocolHarness


class Evaluator:
    def __init__(
        self,
        name: str,
        manifest: ItineraryManifest,
        protocol: ProtocolHarness,
        ledger: AtomicLedger,
    ) -> None:
        self.name = name
        self.manifest = manifest
        self.protocol = protocol
        self.ledger = ledger
        self.ledger.initialize(manifest.itinerary_id, manifest.budget_minor)

    def decide(self, artifacts: ProtocolArtifacts) -> Decision:
        spent, uses = self.ledger.context(self.manifest.itinerary_id)
        verified = self.protocol.verify(artifacts, spent_minor=spent, total_uses=uses)
        if not verified.valid:
            return Decision(False, verified.reason)

        if self.name in {"ap2_plus_parity_policy", "trustbound"}:
            violations = itinerary_violations(self.manifest, artifacts.fact)
            if violations:
                return Decision(False, "itinerary:" + "|".join(violations))

        reservation = self.ledger.reserve(
            self.manifest.itinerary_id,
            artifacts.fact.transaction_id,
            artifacts.fact.amount_minor,
        )
        if not reservation.permitted:
            return reservation
        if self.name == "trustbound":
            commitment = evidence_commitment(
                self.manifest,
                artifacts.fact,
                verified.checkout_hash or artifacts.checkout_hash,
            )
            return Decision(True, "reserved_with_itinerary_evidence", commitment)
        return Decision(True, "reserved")

