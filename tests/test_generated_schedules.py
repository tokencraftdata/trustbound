"""Check oracle sensitivity, including implementations that violate the contract."""
import pytest

from research.service_refinement.check_schedules import FAULTS, cases, run_case
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("fault", FAULTS)
@pytest.mark.parametrize("restart", [False, True])
@pytest.mark.parametrize("cancel", [False, True])
def test_representative_schedules(tmp_path, fault, restart, cancel):
    order = ("grant", "fence", "dispatch", "observe") + (("cancel",) if cancel else ())
    result = run_case(tmp_path, order, fault, restart)
    assert result["resolved"] == (cancel or fault != "abandoned_claim")


def test_schedule_space_is_deterministic_and_complete_for_declared_bound():
    schedules = list(cases())
    assert len(schedules) == len(set(schedules)) == 864
    assert schedules == list(cases())
    assert {len(order) for order, _, _ in schedules} == {4, 5}


class MissingFence(StripeGate):
    def _open(self):
        pass


class RepeatClaim(StripeGate):
    def claim(self, command_id):
        self.db.execute("UPDATE command SET claimed=0 WHERE id=?", (command_id,))
        return super().claim(command_id)


class PrematureClosure(StripeGate):
    def snapshot(self):
        result = super().snapshot()
        result["known_manifest_resolved"] = result["closed"]
        return result


class MissingJournal(StripeGate):
    def snapshot(self):
        result = super().snapshot()
        result["records"] = []
        return result


@pytest.mark.parametrize("gate_type,order,reason", [
    (MissingFence, ("fence", "grant", "dispatch", "observe"), "expected rejected, got ok"),
    (RepeatClaim, ("grant", "dispatch", "fence", "observe"), "expected rejected, got ok"),
    (PrematureClosure, ("grant", "fence", "dispatch", "observe"), "premature or missing closure"),
    (MissingJournal, ("grant", "fence", "dispatch", "observe"), "journal or observations"),
])
def test_checker_rejects_broken_implementations(tmp_path, gate_type, order, reason):
    with pytest.raises(ValueError, match=reason):
        run_case(tmp_path, order, "normal", True, gate_type=gate_type)
