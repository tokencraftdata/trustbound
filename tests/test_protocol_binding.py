"""Authorization decisions must use the authenticated checkout and actual request."""
from copy import deepcopy
from dataclasses import replace

import pytest

from trustbound.baselines import Evaluator
from trustbound.experiment import manifest, scenario_fact
from trustbound.ledger import AtomicLedger
from trustbound.protocol import ProtocolHarness


@pytest.fixture
def payment():
    trip = manifest(9001)
    harness = ProtocolHarness(trip)
    return trip, harness, harness.issue(scenario_fact(trip, "valid", 9001))


@pytest.mark.parametrize("field,value", [
    ("amount_minor", 1), ("currency", "EUR"), ("merchant_name", "Other merchant"),
    ("merchant_id", "other"), ("itinerary_id", "other-trip"), ("transaction_id", "other-tx"),
    ("checkout_id", "other-checkout"), ("item_id", "other-item"), ("title", "Other item"),
    ("leg", "hotel"), ("origin", "AAA"), ("destination", "BBB"),
    ("start", "different-start"), ("end", "different-end"), ("city", "Different city"),
    ("refundable", False),
])
def test_unsigned_fact_cannot_override_authenticated_checkout(payment, field, value):
    _, harness, artifacts = payment
    forged = replace(artifacts, fact=replace(artifacts.fact, **{field: value}))
    assert not harness.verify(forged).valid


def test_success_returns_new_facts_derived_from_signed_checkout(payment):
    _, harness, artifacts = payment
    verified = harness.verify(artifacts)
    assert verified.valid
    assert verified.fact == artifacts.fact
    assert verified.fact is not artifacts.fact


@pytest.mark.parametrize("change", ["payment_token", "checkout_mandate", "extra_instrument", "unselected"])
def test_completion_request_must_contain_the_verified_mandates(payment, change):
    _, harness, artifacts = payment
    request = deepcopy(artifacts.completion_request)
    instrument = request["payment"]["instruments"][0]
    if change == "payment_token":
        instrument["credential"]["token"] = "unverified-token"
    elif change == "checkout_mandate":
        request["ap2"]["checkout_mandate"] = "unverified-checkout"
    elif change == "extra_instrument":
        request["payment"]["instruments"].append(deepcopy(instrument))
    else:
        instrument["selected"] = False
    assert not harness.verify(replace(artifacts, completion_request=request)).valid


def test_forged_amount_does_not_create_a_smaller_reservation(payment):
    trip, harness, artifacts = payment
    ledger = AtomicLedger()
    try:
        evaluator = Evaluator("trustbound", trip, harness, ledger)
        forged = replace(artifacts, fact=replace(artifacts.fact, amount_minor=1))
        assert not evaluator.decide(forged).permitted
        assert ledger.context(trip.itinerary_id) == (0, 0)
        assert evaluator.decide(artifacts).permitted
        assert ledger.context(trip.itinerary_id) == (artifacts.fact.amount_minor, 1)
    finally:
        ledger.close()


def test_unsigned_itinerary_cannot_hide_a_signed_route_violation(payment):
    trip, harness, _ = payment
    artifacts = harness.issue(scenario_fact(trip, "route_mismatch", 9002))
    forged = replace(artifacts, fact=replace(artifacts.fact, destination=trip.outbound_destination))
    ledger = AtomicLedger()
    try:
        evaluator = Evaluator("trustbound", trip, harness, ledger)
        assert not evaluator.decide(forged).permitted
        assert ledger.context(trip.itinerary_id) == (0, 0)
    finally:
        ledger.close()


def test_decision_uses_verified_snapshot_if_caller_changes_facts(payment, monkeypatch):
    trip, harness, artifacts = payment
    amount = artifacts.fact.amount_minor
    verify = harness.verify

    def verify_then_change_input(*args, **kwargs):
        result = verify(*args, **kwargs)
        artifacts.fact = replace(artifacts.fact, amount_minor=1, destination="OTHER")
        return result

    monkeypatch.setattr(harness, "verify", verify_then_change_input)
    ledger = AtomicLedger()
    try:
        assert Evaluator("trustbound", trip, harness, ledger).decide(artifacts).permitted
        assert ledger.context(trip.itinerary_id) == (amount, 1)
    finally:
        ledger.close()
