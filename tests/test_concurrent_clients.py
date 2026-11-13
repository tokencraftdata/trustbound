"""Check concurrent safety scenarios and verify serialized provider reconciliation."""
import pytest

from research.concurrent_clients.evaluate import (
    admission_race, cancellation_race, contention, stale_reconciliation,
)
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("payments", [2, 4])
@pytest.mark.parametrize("fault", ["normal", "lost_reply", "pending_last"])
def test_contending_clients_preserve_each_identity(tmp_path, payments, fault):
    result = contention(tmp_path, 4, payments, fault)
    assert result["capture_invocations"] == payments
    assert result["paid_effects"] == payments - int(fault == "pending_last")
    assert result["resolved"] == (fault != "pending_last")


@pytest.mark.parametrize("operation", ["register", "grant"])
@pytest.mark.parametrize("winner", ["admit", "fence"])
def test_fence_serializes_with_overlapping_admission(tmp_path, operation, winner):
    result = admission_race(tmp_path, operation, winner)
    assert result["resolved"]
    assert result["paid_effects"] == result["capture_invocations"] == 0


@pytest.mark.parametrize("order", ["cancel_first", "capture_first"])
@pytest.mark.parametrize("fault", ["normal", "lost_reply"])
def test_fence_and_retry_during_capture_cancel_race(tmp_path, order, fault):
    result = cancellation_race(tmp_path, order, fault)
    assert result["resolved"]
    assert result["paid_effects"] == (1 if order == "cancel_first" else 2)
    assert result["capture_invocations"] == 2


@pytest.mark.parametrize("terminal", ["succeeded", "canceled"])
def test_overlapping_truthful_reads_resolve_without_false_conflict(tmp_path, terminal):
    result = stale_reconciliation(tmp_path, terminal)
    assert result["conflict_free_reconciliation"]
    assert result["resolved"]
    assert result["outstanding_rights"] == 0
    assert result["observation_conflicts"] == 0


class RepeatClaim(StripeGate):
    def claim(self, command_id):
        self.db.execute("UPDATE command SET claimed=0 WHERE id=?", (command_id,))
        return super().claim(command_id)


class PrematureClosure(StripeGate):
    def snapshot(self):
        result = super().snapshot()
        result["known_manifest_resolved"] = result["closed"]
        return result


class DropIdentity(StripeGate):
    def snapshot(self):
        result = super().snapshot()
        result["records"] = result["records"][:-1]
        return result


@pytest.mark.parametrize("gate_type,message", [
    (RepeatClaim, "extra or missing capture invocation"),
    (PrematureClosure, "premature or missing closure"),
    (DropIdentity, "journal membership differs"),
])
def test_checker_rejects_duplicate_send_early_closure_and_missing_identity(tmp_path, gate_type, message):
    with pytest.raises(ValueError, match=message):
        contention(tmp_path, 2, 2, "pending_last", gate_type=gate_type)


class UnserializedRead(StripeGate):
    def reconcile(self, payment_id, retrieve):
        self.observe(retrieve(payment_id))


def test_checker_rejects_unserialized_provider_read(tmp_path):
    with pytest.raises(ValueError, match="provider read was not serialized|overtook"):
        stale_reconciliation(tmp_path, "canceled", gate_type=UnserializedRead)
