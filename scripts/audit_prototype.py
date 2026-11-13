"""Check terminality, signing-key persistence, and reservation accounting.

These are local regression probes, not a deployment security proof.
"""
import argparse
import json
from pathlib import Path
import tempfile

from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor, verify_statement


def run():
    with tempfile.TemporaryDirectory(prefix="trustbound-gap-") as tmp:
        root = Path(tmp)
        processor = FencedProcessor("p", root / "p.db")
        processor.open_epoch("e")
        processor.admit("e", "old", "flight", 100, 1)
        processor.reconcile("old", "released", None)
        certificate = processor.close_epoch("e")
        try:
            processor.reconcile("old", "confirmed", "late-debit")
        except RuntimeError as exc:
            assert str(exc) == "terminal_payment_conflict"
        row = processor._connection.execute(
            "SELECT status FROM payment WHERE payment_id = 'old'"
        ).fetchone()
        stale_zero = row[0] == "confirmed" and verify_statement(certificate, processor.public_key).liability_minor == 0
        key = processor.public_key
        processor.close()
        reopened = FencedProcessor("p", root / "p.db")
        key_changes = reopened.public_key != key
        reopened.open_epoch("next")
        coordinator = PersistentCoordinator("flight", 100, root / "flight.db")
        coordinator.reserve_quote("q", 1, 100)
        coordinator.submit(reopened, "next", "q", 1, "first")
        try:
            coordinator.submit(reopened, "next", "q", 1, "duplicate")
        except RuntimeError as exc:
            assert str(exc) == "submission_conflict"
        try:
            coordinator.reserve_quote("q", 2, 100)
        except RuntimeError as exc:
            assert str(exc) == "allocation_exceeded"
        liability = coordinator.snapshot()["liability_minor"]
        old_state = coordinator.snapshot()["quotes"][0][3]
        admitted = reopened._connection.execute(
            "SELECT SUM(amount_minor) FROM payment WHERE epoch_id = 'next'"
        ).fetchone()[0]
        coordinator.close()
        reopened.close()
    return {
        "status": "prototype_not_a_refinement_of_the_Lean_model",
        "released_then_confirmed_leaves_valid_zero_certificate": stale_zero,
        "processor_signing_identity_changes_on_restart": key_changes,
        "two_submissions_from_one_reservation": admitted == 200,
        "submitted_quote_revision_releases_old_reservation": old_state == "released",
        "liability_minor": liability,
        "admitted_minor": admitted,
        "warning": "False defect flags are local regressions only, not real payment completeness or end-to-end security. Do not deploy.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
