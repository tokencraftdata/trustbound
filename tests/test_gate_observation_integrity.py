import json
import sqlite3

import pytest

from trustbound.credential_service import CommandService, intent
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("command_state", ["absent", "unclaimed_capture", "claimed_confirm", "other_payment"])
def test_paid_report_requires_own_claimed_capture(tmp_path, command_state):
    path = tmp_path / "gate.db"
    gate = StripeGate(path, "epoch")
    gate.register(intent())
    if command_state == "unclaimed_capture":
        gate.grant("pi_Boundary1", "capture")
    elif command_state == "claimed_confirm":
        gate.claim(gate.grant("pi_Boundary1", "confirm"))
    elif command_state == "other_payment":
        gate.register({**intent(), "id": "pi_Other"})
        gate.claim(gate.grant("pi_Other", "capture"))
    gate.fence()
    with pytest.raises(RuntimeError, match="paid_without_claimed_capture"):
        gate.observe(intent("succeeded"))
    gate.close()
    reopened = StripeGate(path, "epoch")
    state = reopened.snapshot()
    assert state["has_contract_conflicts"] and not state["known_manifest_resolved"]
    assert not state["deployment_completeness_proved"]
    assert state["records"][0]["status"] == "uncertain"
    reopened.close()


def test_valid_capture_report_and_duplicate_observation(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.claim(gate.grant("pi_Boundary1", "capture"))
    gate.fence()
    gate.observe(intent("succeeded"))
    gate.observe(intent("succeeded"))
    state = gate.snapshot()
    assert state["known_manifest_resolved"] and not state["has_contract_conflicts"]
    assert state["retained_minor"] == 200
    gate.close()


@pytest.mark.parametrize("conflicting", [intent("succeeded"), intent("processing"), {**intent("canceled"), "amount": 201}])
def test_terminal_conflict_survives_restart_and_matching_report(tmp_path, conflicting):
    path = tmp_path / "gate.db"
    gate = StripeGate(path, "epoch")
    gate.register(intent())
    gate.observe(intent("canceled"))
    gate.fence()
    assert gate.snapshot()["known_manifest_resolved"]
    with pytest.raises((ValueError, RuntimeError)):
        gate.observe(conflicting)
    gate.close()
    gate = StripeGate(path, "epoch")
    gate.observe(intent("canceled"))
    state = gate.snapshot()
    assert state["has_contract_conflicts"] and not state["known_manifest_resolved"]
    assert state["retained_minor"] == 200
    gate.close()


def test_conflicted_payment_cannot_gain_or_claim_commands(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    command = gate.grant("pi_Boundary1", "capture")
    with pytest.raises(RuntimeError, match="paid_without_claimed_capture"):
        gate.observe(intent("succeeded"))
    with pytest.raises(RuntimeError, match="payment_contract_conflict"):
        gate.grant("pi_Boundary1", "confirm")
    with pytest.raises(RuntimeError, match="payment_contract_conflict"):
        gate.claim(command)
    gate.close()


def test_conflict_is_visible_through_request_only_interface(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(intent())
    gate.fence()

    class ContradictoryProvider:
        def retrieve(self, _):
            return intent("succeeded")

    service = CommandService(gate, ContradictoryProvider())
    assert not service.handle(b'{"op":"reconcile"}')["ok"]
    reply = service.handle(b'{"op":"snapshot"}')["result"]
    assert reply["has_contract_conflicts"] and not reply["known_manifest_resolved"]
    assert "pi_Boundary1" not in json.dumps(reply)
    gate.close()


def test_legacy_paid_row_without_provenance_cannot_resolve(tmp_path):
    path = tmp_path / "gate.db"
    # Exact previous schema: migration may not trust a historical resolved flag.
    with sqlite3.connect(path) as db:
        db.executescript("""
        CREATE TABLE epoch(id TEXT PRIMARY KEY, closed INTEGER NOT NULL);
        CREATE TABLE payment(id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
          status TEXT NOT NULL, received INTEGER NOT NULL, capturable INTEGER NOT NULL);
        CREATE TABLE command(id INTEGER PRIMARY KEY, payment_id TEXT NOT NULL,
          action TEXT NOT NULL, claimed INTEGER NOT NULL DEFAULT 0, UNIQUE(payment_id, action));
        INSERT INTO epoch VALUES ('epoch', 1);
        INSERT INTO payment VALUES ('pi_Boundary1', 200, 'succeeded', 200, 0);
        """)
    gate = StripeGate(path, "epoch")
    state = gate.snapshot()
    assert state["has_contract_conflicts"] and not state["known_manifest_resolved"]
    gate.close()
