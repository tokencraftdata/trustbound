from concurrent.futures import ThreadPoolExecutor

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

