import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def probe(monkeypatch):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("controlled_merchant", scripts / "validate_controlled_merchant.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence():
    before = {kind: {"records": []} for kind in ("payment_intents", "charges")}
    after = {"payment_intents": {"records": [{"id": "pi_A", "status": "succeeded", "amount_received": 200,
        "amount_capturable": 0, "currency": "usd", "latest_charge": "ch_A"}]},
        "charges": {"records": [{"id": "ch_A", "payment_intent": "pi_A", "amount_captured": 200,
                                 "currency": "usd", "captured": True, "status": "succeeded"}]}}
    snapshot = {"records": [{"id": "pi_A", "status": "succeeded", "amount": 200, "received": 200}]}
    return before, after, snapshot


def test_matching_provider_views_remain_conditional(probe):
    result = probe.reconcile_delta(*evidence())
    assert result["observed_delta_matches_manifest"]
    assert not result["account_completeness_established"]
    assert not result["atomic_snapshot"] and not result["independent_issuer"]


@pytest.mark.parametrize("corruption", ["hidden_intent", "hidden_charge", "missing_charge", "wrong_amount", "prior_object_changed", "empty_manifest"])
def test_reconciliation_refuses_missing_or_mismatched_evidence(probe, corruption):
    before, after, snapshot = evidence()
    if corruption == "hidden_intent":
        after["payment_intents"]["records"].append({"id": "pi_hidden"})
    elif corruption == "hidden_charge":
        after["charges"]["records"].append({"id": "ch_hidden", "payment_intent": "pi_hidden"})
    elif corruption == "missing_charge":
        after["charges"]["records"] = []
    elif corruption == "wrong_amount":
        after["charges"]["records"][0]["amount_captured"] = 100
    elif corruption == "prior_object_changed":
        before["payment_intents"]["records"].append({"id": "pi_old", "status": "requires_capture"})
        after["payment_intents"]["records"].append({"id": "pi_old", "status": "succeeded"})
    else:
        snapshot["records"] = []
    assert not probe.reconcile_delta(before, after, snapshot)["observed_delta_matches_manifest"]


def test_application_reply_discard_does_not_resend(probe):
    class API:
        def __init__(self):
            self.calls = []
        def request(self, *args):
            self.calls.append(args)
            return 200, {"status": "succeeded"}
    api = API()
    adapter = probe.FixedAdapter(api)
    with pytest.raises(TimeoutError):
        adapter.request("POST", "/v1/payment_intents/pi_A/capture", {}, "run:1")
    assert len(api.calls) == 1


def test_failed_authoritative_read_is_not_an_observation(probe):
    class API:
        def request(self, *args):
            return 403, {}
    with pytest.raises(RuntimeError, match="authoritative_read_failed"):
        probe.FixedAdapter(API()).retrieve("pi_A")
