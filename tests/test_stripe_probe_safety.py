import importlib.util
from pathlib import Path

import pytest

from trustbound.sandbox_observer import StripeSandboxObserver


def module(filename="validate_stripe_sandbox.py"):
    spec = importlib.util.spec_from_file_location("stripe_probe", Path(__file__).parents[1] / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_claimable_sandbox_test_key_format_is_supported():
    StripeSandboxObserver("rkcs_test_fixture")


@pytest.mark.parametrize("key", ["rkcs_live_fixture", "sk_live_fixture", "rk_live_fixture", "pk_test_fixture"])
def test_probe_rejects_live_and_publishable_keys_before_journal(tmp_path, key):
    with pytest.raises(ValueError, match="test_mode_key_required"):
        module().ProbeClient(key, tmp_path, "test-run")
    assert not (tmp_path / "request-journal.db").exists()


@pytest.mark.parametrize("method,path,body,idem", [
    ("DELETE", "/v1/payment_intents/pi_fixture", None, None),
    ("GET", "https://other.invalid", None, None),
    ("POST", "/v1/charges", {}, "test-run:a"),
    ("POST", "/v1/payment_intents", {"amount": 1001}, "test-run:a"),
    ("POST", "/v1/payment_intents", {"amount": True}, "test-run:a"),
    ("POST", "/v1/payment_intents", {"amount": 100, "currency": "eur"}, "test-run:a"),
    ("POST", "/v1/payment_intents/pi_fixture/capture", {}, None),
    ("POST", "/v1/payment_intents/pi_fixture/confirm", {"payment_method": "pm_real"}, "test-run:a"),
])
def test_invalid_probe_requests_never_dispatch(tmp_path, method, path, body, idem):
    api = module().ProbeClient("rkcs_test_fixture", tmp_path, "test-run")
    with pytest.raises(ValueError):
        api.request(method, path, body, idem)
    assert api.db.execute("SELECT COUNT(*) FROM request").fetchone()[0] == 0
    api.db.close()


def test_report_projection_drops_secrets_and_personal_data():
    safe = module().safe_payment({"id": "pi_test", "client_secret": "secret",
                                  "receipt_email": "private@example.invalid", "shipping": "private"})
    assert safe["id"] == "pi_test"
    assert "client_secret" not in safe
    assert "receipt_email" not in safe
    assert "shipping" not in safe


def test_account_comparison_rejects_unknown_charge_and_amount_mismatch():
    compare = module("reconcile_stripe_account.py").compare
    p = {"records": [{"id": "pi_p", "amount_received": 100, "currency": "usd", "status": "succeeded"}]}
    c = {"records": [{"id": "ch_c", "payment_intent": "pi_p", "amount_captured": 100, "currency": "usd"}]}
    assert compare(p, c)["all_compared_amounts_match"]
    c["records"][0]["amount_captured"] = 99
    assert not compare(p, c)["all_compared_amounts_match"]
    c["records"][0]["payment_intent"] = "pi_unknown"
    assert compare(p, c)["unmatched_charge_ids"] == ["ch_c"]


def test_account_comparison_cannot_certify_empty_or_complete_epoch():
    result = module("reconcile_stripe_account.py").compare({"records": []}, {"records": []})
    assert not result["all_compared_amounts_match"]
    assert not result["epoch_completeness_established"]
