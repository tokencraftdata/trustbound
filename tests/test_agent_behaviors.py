"""Exercise outcome differences and challenge the independent client-check oracle."""
import pytest

from research.agent_behaviors.evaluate import run_case
from trustbound.credential_service import CommandService
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("fault,closed", [
    ("normal", True), ("lost_reply", True), ("pending_provider", False), ("terminal_cancel", True),
])
@pytest.mark.parametrize("restart", [False, True])
def test_reconciliation_distinguishes_terminal_outcomes_from_pending_work(tmp_path, fault, closed, restart):
    result = run_case(tmp_path, "reconcile_after_attempt", fault, restart)
    assert result["resolved_after_agent"] == closed
    assert result["resolved_after_operator"] == closed
    assert result["capture_invocations"] == 1


@pytest.mark.parametrize("policy", ["single_attempt", "bounded_retry", "snapshot_polling"])
def test_lost_reply_needs_reconciliation_not_retries_or_local_polls(tmp_path, policy):
    result = run_case(tmp_path, policy, "lost_reply", True)
    assert result["paid_effects"] == 1
    assert not result["resolved_after_agent"]
    assert result["resolved_after_operator"]
    assert result["history"][-1]["actor"] == "operator"


def test_invalid_requests_cannot_change_approved_scope(tmp_path):
    result = run_case(tmp_path, "invalid_and_replayed_requests", "normal", True)
    assert all(not event["response"]["ok"] for event in result["history"][:5])
    assert result["agent_dispatch_requests"] == 3
    assert result["capture_invocations"] == result["paid_effects"] == 1


class RepeatClaim(StripeGate):
    def claim(self, command_id):
        self.db.execute("UPDATE command SET claimed=0 WHERE id=?", (command_id,))
        return super().claim(command_id)


class PrematureClosure(StripeGate):
    def snapshot(self):
        result = super().snapshot()
        result["known_manifest_resolved"] = result["closed"]
        return result


class TrustForgedRequest(CommandService):
    def handle(self, raw):
        if b'"observe"' in raw:
            return {"ok": True, "result": {"known_manifest_resolved": True}}
        return super().handle(raw)


@pytest.mark.parametrize("gate_type,service_type", [
    (RepeatClaim, CommandService), (PrematureClosure, CommandService),
    (StripeGate, TrustForgedRequest),
])
def test_evaluator_rejects_repeated_dispatch_premature_closure_and_forged_reports(tmp_path, gate_type, service_type):
    with pytest.raises(ValueError, match="differs from expected contract"):
        run_case(tmp_path, "invalid_and_replayed_requests", "normal", True,
                 gate_type=gate_type, service_type=service_type)
