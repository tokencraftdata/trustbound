from dataclasses import replace

from trustbound.experiment import manifest, scenario_fact
from trustbound.protocol import ProtocolHarness


def test_official_sdk_round_trip():
    m = manifest(1)
    harness = ProtocolHarness(m)
    artifacts = harness.issue(scenario_fact(m, "valid", 1))
    result = harness.verify(artifacts)
    assert result.valid
    assert artifacts.checkout["ucp"]["version"] == "2026-08-25"
    assert "~~" in artifacts.checkout_mandate
    assert "~~" in artifacts.payment_mandate


def test_tampered_ap2_mandate_fails_closed():
    m = manifest(2)
    harness = ProtocolHarness(m)
    artifacts = harness.issue(scenario_fact(m, "valid", 2))
    replacement = "A" if artifacts.checkout_mandate[-1] != "A" else "B"
    tampered = replace(artifacts, checkout_mandate=artifacts.checkout_mandate[:-1] + replacement)
    assert not harness.verify(tampered).valid


def test_stateful_ap2_budget_context_is_used():
    m = manifest(3)
    harness = ProtocolHarness(m)
    artifacts = harness.issue(scenario_fact(m, "aggregate_overspend", 3))
    result = harness.verify(artifacts, spent_minor=299_000, total_uses=1)
    assert not result.valid
    assert "budget" in result.reason.lower()


def test_terminal_audience_and_nonce_are_checked():
    m = manifest(4)
    harness = ProtocolHarness(m)
    artifacts = harness.issue(scenario_fact(m, "valid", 4))
    changed_fact = replace(artifacts.fact, transaction_id="wrong-nonce")
    changed = replace(artifacts, fact=changed_fact)
    result = harness.verify(changed)
    assert not result.valid
