import sqlite3
import pytest
from trustbound.stripe_gate import StripeGate


def intent(**changes):
    return {"id": "pi_Test1", "object": "payment_intent", "livemode": False,
            "amount": 200, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": "requires_payment_method",
            "amount_received": 0, "amount_capturable": 0, **changes}


def test_unregistered_cannot_grant(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    with pytest.raises(RuntimeError, match="unknown_or_terminal"):
        gate.grant("pi_Unknown", "confirm")
    assert gate.snapshot()["records"] == []
    gate.close()


@pytest.mark.parametrize("change", [
    {"confirmation_method": "automatic"}, {"capture_method": "automatic"},
    {"status": "requires_capture"}, {"livemode": True},
    {"payment_method": "pm_AlreadyAttached"}, {"customer": "cus_Existing"},
    {"payment_method_types": ["card", "link"]}, {"amount_received": 100},
])
def test_unsafe_registration_rejected(tmp_path, change):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    with pytest.raises(ValueError, match="not_inert"):
        gate.register(intent(**change))
    gate.close()


def test_fence_survives_restart_and_covers_prior_dispatch(tmp_path):
    path = tmp_path / "gate.db"
    gate = StripeGate(path, "epoch")
    gate.register(intent())
    command = gate.grant("pi_Test1", "confirm")
    gate.fence()
    gate.close()
    gate = StripeGate(path, "epoch")
    with pytest.raises(RuntimeError, match="fenced"):
        gate.grant("pi_Test1", "capture")
    with pytest.raises(RuntimeError, match="fenced"):
        gate.register(intent(id="pi_Test2"))
    assert gate.claim(command) == ("pi_Test1", "confirm")
    gate.close()
    gate = StripeGate(path, "epoch")
    with pytest.raises(RuntimeError, match="already_claimed"):
        gate.claim(command)
    assert gate.snapshot()["retained_minor"] == 200
    assert not gate.snapshot()["known_manifest_resolved"]
    gate.close()


def test_terminal_outcomes_and_no_local_reopen(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.fence()
    gate.observe(intent(status="processing"))
    assert not gate.snapshot()["known_manifest_resolved"]
    gate.observe(intent(status="canceled"))
    assert gate.snapshot()["known_manifest_resolved"]
    assert not gate.snapshot()["deployment_completeness_proved"]
    with pytest.raises(RuntimeError, match="terminal_observation_changed"):
        gate.observe(intent())
    assert gate.snapshot()["retained_minor"] == 200
    assert gate.snapshot()["has_contract_conflicts"]
    assert not gate.snapshot()["known_manifest_resolved"]
    gate.close()


def test_scope_mismatch_never_resolves(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.claim(gate.grant("pi_Test1", "capture"))
    gate.fence()
    with pytest.raises(ValueError, match="scope_mismatch"):
        gate.observe(intent(status="succeeded", amount=201, amount_received=201))
    assert gate.snapshot()["retained_minor"] == 200
    gate.observe(intent(status="succeeded", amount_received=200))
    assert not gate.snapshot()["known_manifest_resolved"]
    assert gate.snapshot()["has_contract_conflicts"]
    assert gate.snapshot()["retained_minor"] == 200
    gate.close()


def test_other_connection_observes_fence(tmp_path):
    path = tmp_path / "gate.db"
    first, second = StripeGate(path, "epoch"), StripeGate(path, "epoch")
    first.register(intent())
    second.fence()
    with pytest.raises(RuntimeError, match="fenced"):
        first.grant("pi_Test1", "confirm")
    first.close()
    second.close()


def test_duplicate_command_and_epoch_mismatch(tmp_path):
    path = tmp_path / "gate.db"
    gate = StripeGate(path, "epoch")
    gate.register(intent())
    gate.grant("pi_Test1", "confirm")
    with pytest.raises(sqlite3.IntegrityError):
        gate.grant("pi_Test1", "confirm")
    gate.close()
    with pytest.raises(ValueError, match="epoch_identity_mismatch"):
        StripeGate(path, "other-epoch")


def test_terminal_observation_discharges_unclaimed_commands(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch-terminal")
    gate.register(intent())
    confirm = gate.grant("pi_Test1", "confirm")
    capture = gate.grant("pi_Test1", "capture")
    gate.fence()
    gate.observe(intent(status="canceled"))
    assert gate.snapshot()["known_manifest_resolved"]
    for command in (confirm, capture):
        with pytest.raises(RuntimeError, match="payment_terminal"):
            gate.claim(command)
    calls = []

    class Transport:
        def request(self, *args):
            calls.append(args)
            return 200, {}

    with pytest.raises(RuntimeError, match="payment_terminal"):
        gate.dispatch(capture, Transport())
    assert calls == []
    gate.close()
    reopened = StripeGate(tmp_path / "gate.db", "epoch-terminal")
    with pytest.raises(RuntimeError, match="payment_terminal"):
        reopened.claim(capture)
    snapshot = reopened.snapshot()
    assert snapshot["known_manifest_resolved"]
    assert all(not command["claimed"] for command in snapshot["commands"])
