from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from trustbound.experiment import manifest, scenario_fact
from trustbound.ledger import AtomicLedger
from trustbound.policy import itinerary_violations


def test_itinerary_policy_detects_cross_provider_mismatch():
    m = manifest(10)
    assert itinerary_violations(m, scenario_fact(m, "valid", 10)) == []
    assert "outbound_route_or_time" in itinerary_violations(
        m, scenario_fact(m, "route_mismatch", 10)
    )


def test_atomic_budget_under_concurrency():
    ledger = AtomicLedger()
    ledger.initialize("trip", 5_000)
    with ThreadPoolExecutor(max_workers=20) as pool:
        decisions = list(pool.map(lambda i: ledger.reserve("trip", f"tx-{i}", 100), range(100)))
    spent, uses = ledger.context("trip")
    assert sum(item.permitted for item in decisions) == 50
    assert spent == 5_000
    assert uses == 50


def test_replay_is_rejected():
    ledger = AtomicLedger()
    ledger.initialize("trip", 1_000)
    assert ledger.reserve("trip", "same", 100).permitted
    assert ledger.reserve("trip", "same", 100).reason == "replay"


@pytest.mark.parametrize("amount", [-10_000, True, False, 1.5, "100", None, 2**63])
def test_invalid_reservation_cannot_create_capacity_or_consume_identity(tmp_path, amount):
    path = tmp_path / "ledger.db"
    with closing(AtomicLedger(path)) as ledger:
        ledger.initialize("trip", 50_000)
        assert ledger.reserve("trip", "invalid", amount).reason == "invalid_amount"
        assert ledger.context("trip") == (0, 0)
        assert ledger.reserve("trip", "oversized", 60_000).reason == "aggregate_budget"
    with closing(AtomicLedger(path)) as ledger:
        assert ledger.context("trip") == (0, 0)
        assert ledger.reserve("trip", "invalid", 50_000).permitted
        assert ledger.reserve("trip", "extra", 1).reason == "aggregate_budget"


@pytest.mark.parametrize("limit", [-1, True, False, 1.5, "100", None, 2**63])
def test_invalid_budget_is_rejected_before_initialization(limit):
    with closing(AtomicLedger()) as ledger:
        with pytest.raises(ValueError, match="invalid_budget"):
            ledger.initialize("trip", limit)
        with pytest.raises(KeyError):
            ledger.context("trip")
        ledger.initialize("trip", 100)
        assert ledger.reserve("trip", "valid", 100).permitted


@pytest.mark.parametrize("limit", [0, 2**63 - 1])
def test_exact_integer_budget_boundaries(limit):
    with closing(AtomicLedger()) as ledger:
        ledger.initialize("trip", limit)
        assert ledger.reserve("trip", "valid", limit).permitted
        assert ledger.context("trip") == (limit, 1)
        assert ledger.reserve("trip", "extra", 1).reason == "aggregate_budget"

