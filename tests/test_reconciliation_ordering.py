"""Ordered retrieval preserves contradictions and releases locks on failure."""
from contextlib import closing
import multiprocessing
import time

import pytest

from trustbound.credential_service import intent
from trustbound.stripe_gate import StripeGate


@pytest.mark.parametrize("contradiction", [
    intent("requires_capture"), intent("succeeded"),
    {**intent("canceled"), "amount": 201},
])
def test_serialized_retrieval_still_records_real_contradictions(tmp_path, contradiction):
    path = tmp_path / "gate.db"
    with closing(StripeGate(path, "epoch")) as gate:
        gate.register(intent())
        gate.fence()
        gate.reconcile("pi_Boundary1", lambda _: intent("canceled"))
        with pytest.raises((RuntimeError, ValueError)):
            gate.reconcile("pi_Boundary1", lambda _: contradiction)
    with closing(StripeGate(path, "epoch")) as gate:
        gate.reconcile("pi_Boundary1", lambda _: intent("canceled"))
        state = gate.snapshot()
        assert state["has_contract_conflicts"]
        assert not state["known_manifest_resolved"]
        assert state["records"][0]["status"] == "canceled"


def test_retrieval_identity_is_bound_to_requested_payment(tmp_path):
    path = tmp_path / "gate.db"
    with closing(StripeGate(path, "epoch")) as gate:
        gate.register(intent())
        gate.register({**intent(), "id": "pi_Other"})
        gate.fence()
        with pytest.raises(ValueError, match="observation_identity_mismatch"):
            gate.reconcile("pi_Boundary1", lambda _: {**intent("canceled"), "id": "pi_Other"})
    with closing(StripeGate(path, "epoch")) as gate:
        state = gate.snapshot()
        assert all(row["status"] == "uncertain" for row in state["records"])
        assert state["contract_conflicts"] == [{
            "payment_id": "pi_Boundary1", "reason": "observation_identity_mismatch",
        }]


def test_retrieval_failure_rolls_back_and_allows_another_connection(tmp_path):
    path = tmp_path / "gate.db"
    with closing(StripeGate(path, "epoch")) as gate:
        gate.register(intent())
        gate.fence()
        before = gate.snapshot()

        def timeout(_):
            raise TimeoutError("provider unavailable")

        with pytest.raises(TimeoutError):
            gate.reconcile("pi_Boundary1", timeout)
        assert not gate.db.in_transaction
        assert gate.snapshot() == before
        with closing(StripeGate(path, "epoch")) as other:
            other.reconcile("pi_Boundary1", lambda _: intent("canceled"))
            assert other.snapshot()["known_manifest_resolved"]


def _blocked_reconciliation(path, entered):
    with closing(StripeGate(path, "epoch")) as gate:
        def retrieve(_):
            entered.set()
            time.sleep(15)  # Parent kills this worker while retrieval is active.
            return intent("canceled")
        gate.reconcile("pi_Boundary1", retrieve)


def test_process_death_releases_retrieval_transaction(tmp_path):
    path = tmp_path / "gate.db"
    with closing(StripeGate(path, "epoch")) as gate:
        gate.register(intent())
        gate.fence()
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    worker = context.Process(target=_blocked_reconciliation, args=(path, entered))
    worker.start()
    try:
        assert entered.wait(10), "worker did not start retrieval"
        worker.terminate()
        worker.join(10)
        assert not worker.is_alive()
        with closing(StripeGate(path, "epoch")) as gate:
            assert not gate.snapshot()["known_manifest_resolved"]
            gate.reconcile("pi_Boundary1", lambda _: intent("canceled"))
            assert gate.snapshot()["known_manifest_resolved"]
    finally:
        if worker.is_alive():
            worker.kill()
        worker.join(10)
        worker.close()
