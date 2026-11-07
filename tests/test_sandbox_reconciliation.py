"""Offline transport fixtures only; no sandbox API execution is claimed."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from trustbound.reconciliation import compare_records
from trustbound.sandbox_observer import ObservationError, StripeSandboxObserver, _NoRedirect


def intent(**overrides):
    return {
        "object": "payment_intent", "id": "pi_fixture", "amount": 100,
        "amount_received": 100, "amount_capturable": 0, "currency": "usd",
        "status": "succeeded", "livemode": False,
        "client_secret": "MUST_NOT_APPEAR", **overrides,
    }


def observer(data):
    return StripeSandboxObserver("sk_test_fixture", transport=lambda *args: data)


def test_observer_uses_only_read_endpoint_and_sanitizes_response():
    requests = []
    def transport(request, timeout):
        requests.append(request)
        assert 0 < timeout <= 30
        return intent()
    result = StripeSandboxObserver("rk_test_fixture", transport=transport).retrieve("pi_fixture")
    assert requests[0].method == "GET"
    assert requests[0].full_url == "https://api.stripe.com/v1/payment_intents/pi_fixture"
    assert requests[0].data is None
    assert result["status"] == "confirmed"
    assert "MUST_NOT_APPEAR" not in json.dumps(result)
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize("key", ["sk_live_fixture", "rk_live_fixture", "pk_test_fixture", "", "sk_test_a\nb"])
def test_non_test_secret_keys_rejected(key):
    with pytest.raises(ValueError, match="test_mode_key_required"):
        StripeSandboxObserver(key)


@pytest.mark.parametrize("patch", [
    {"livemode": True}, {"livemode": None}, {"id": "pi_wrong"},
    {"amount": -1}, {"amount_received": True}, {"amount_capturable": None},
    {"currency": "unknown"}, {"status": "new_unknown_state"},
])
def test_invalid_or_non_sandbox_observations_fail_closed(patch):
    with pytest.raises(ObservationError):
        observer(intent(**patch)).retrieve("pi_fixture")


@pytest.mark.parametrize("status", ["requires_payment_method", "requires_action", "requires_confirmation", "processing", "requires_capture"])
def test_nonterminal_provider_status_never_releases(status):
    assert observer(intent(status=status, amount_received=0)).retrieve("pi_fixture")["status"] == "uncertain"


def test_canceled_partial_capture_is_not_zero_liability():
    assert observer(intent(status="canceled", amount_received=50)).retrieve("pi_fixture")["status"] == "uncertain"
    assert observer(intent(status="canceled", amount_received=0)).retrieve("pi_fixture")["status"] == "released"


def test_timeout_is_observation_failure_not_release():
    def timeout(*args):
        raise TimeoutError()
    with pytest.raises(ObservationError, match="observation_unavailable"):
        StripeSandboxObserver("sk_test_fixture", transport=timeout).retrieve("pi_fixture")


def test_bad_id_and_redirect_rejected():
    with pytest.raises(ValueError, match="invalid_payment_intent_id"):
        observer(intent()).retrieve("../charges")
    with pytest.raises(ObservationError, match="redirect_rejected"):
        _NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.invalid")


def records():
    local, bookings, payments = [], [], []
    for leg in ("flight", "hotel"):
        local.append({
            "leg": leg, "booking_provider": "fixture-" + leg,
            "booking_id": leg + "1", "payment_id": "pi_" + leg,
            "amount_minor": 100, "currency": "usd",
            "booking_status": "confirmed", "payment_status": "confirmed",
        })
        bookings.append({**local[-1], "status": "confirmed", "livemode": False})
        payments.append({**local[-1], "status": "confirmed", "livemode": False})
    return local, bookings, payments


def test_matching_records_never_claim_completeness_or_authenticated_provenance():
    result = compare_records(*records())
    assert result["records_match"]
    assert not result["epoch_completeness_established"]
    assert not result["provenance_authenticated"]


@pytest.mark.parametrize("change", [
    "missing_booking", "missing_payment", "extra_payment", "extra_booking",
    "duplicate_booking", "duplicate_payment", "changed_quote", "currency",
    "partial_failure", "uncertain", "live", "wrong_payment", "empty", "shared_payment",
])
def test_reconciliation_detects_unsafe_or_incomplete_records(change):
    local, bookings, payments = deepcopy(records())
    if change == "missing_booking":
        bookings.pop()
    elif change == "missing_payment":
        payments.pop()
    elif change == "extra_payment":
        payments.append({**payments[0], "payment_id": "pi_extra"})
    elif change == "extra_booking":
        bookings.append({**bookings[0], "booking_id": "extra"})
    elif change == "duplicate_booking":
        bookings.append(bookings[0])
    elif change == "duplicate_payment":
        payments.append(payments[0])
    elif change == "changed_quote":
        bookings[0]["amount_minor"] += 1
    elif change == "currency":
        payments[0]["currency"] = "eur"
    elif change == "partial_failure":
        bookings[0]["status"] = local[0]["booking_status"] = "canceled"
    elif change == "uncertain":
        payments[0]["status"] = local[0]["payment_status"] = "uncertain"
    elif change == "live":
        payments[0]["livemode"] = True
    elif change == "wrong_payment":
        bookings[0]["payment_id"] = "pi_wrong"
    elif change == "empty":
        local, bookings, payments = [], [], []
    elif change == "shared_payment":
        local[1]["payment_id"] = local[0]["payment_id"]
    result = compare_records(local, bookings, payments)
    assert not result["records_match"]
    assert not result["epoch_completeness_established"]


def test_fixture_command_runs_without_network_or_credentials(tmp_path):
    package = Path(__file__).parents[1]
    command = [sys.executable, str(package / "scripts/reconcile_sandbox.py")]
    for flag, data in zip(("--local", "--bookings", "--payment-fixture"), records()):
        path = tmp_path / (flag[2:] + ".json")
        path.write_text(json.dumps(data))
        command.extend([flag, str(path)])
    output = tmp_path / "report.json"
    result = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["payment_acquisition"] == "local_fixture"
    assert report["records_match"]
    assert not report["epoch_completeness_established"]
