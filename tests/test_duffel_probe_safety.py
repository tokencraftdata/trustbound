"""Offline guard tests. These do not exercise Duffel or establish completeness."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "duffel_probe", Path(__file__).parents[1] / "scripts" / "validate_duffel_sandbox.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("key", ["", "duffel_live_example", "duffel_test_***", "Bearer duffel_test_example"])
def test_rejects_unsafe_credentials(key):
    with pytest.raises(ValueError, match="test_token_required"):
        probe.validate_key(key)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1000.01", "0.001"])
def test_cap_uses_exact_finite_minor_units(value):
    with pytest.raises(ValueError, match="quote_outside_synthetic_cap"):
        probe.minor(value)


def test_unknown_attempt_is_not_replayed(tmp_path, monkeypatch):
    instance = probe.Probe(tmp_path, "duffel_test_example")
    (instance.private / "book-request.json").write_text('{"outcome":"unknown"}')
    def forbidden(*args, **kwargs):
        pytest.fail("must not construct transport for attempted stage")
    monkeypatch.setattr(probe, "build_opener", forbidden)
    with pytest.raises(FileExistsError):
        instance.request("book", "POST", "/air/orders", {})


def test_cannot_cancel_another_order(tmp_path, monkeypatch):
    instance = probe.Probe(tmp_path, "duffel_test_example")
    monkeypatch.setattr(instance, "previous", lambda stage: {
        "id": "ord_example", "live_mode": False,
        "metadata": {"trustbound_reference": "different-reference"}})
    with pytest.raises(ValueError, match="own_test_order_binding_required"):
        instance.run("cancel-quote")


def test_booking_cancel_does_not_zero_local_exposure(tmp_path):
    from trustbound.coordinator import PersistentCoordinator
    from trustbound.epoch import FencedProcessor
    processor = FencedProcessor("local-admission-not-duffel", tmp_path / "processor.db")
    coordinator = PersistentCoordinator("flight", 100000, tmp_path / "flight.db")
    processor.open_epoch("epoch")
    coordinator.reserve_quote("quote", 1, 12345)
    coordinator.submit(processor, "epoch", "quote", 1, "payment")
    coordinator.close()
    # A booking-only cancellation record cannot change the payment database.
    (tmp_path / "cancel-confirm-result.json").write_text(json.dumps({
        "record": {"cancelled_at": "2026-11-01T20:00:00Z", "refund_amount": "123.45"}}))
    reopened = PersistentCoordinator("flight", 100000, tmp_path / "flight.db")
    assert reopened.snapshot()["liability_minor"] == 12345
    assert reopened.snapshot()["quotes"][0][3] == "uncertain"
    reopened.close()
    processor.close()


def test_discarded_reply_survives_restart_without_blind_retry(tmp_path, monkeypatch):
    class Response:
        code = 201
        headers = {"x-request-id": "fixture"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, size): return b'{"data":{"id":"ord_fixture","live_mode":false}}'
    class Opener:
        def open(self, *args, **kwargs): return Response()
    monkeypatch.setattr(probe, "build_opener", lambda *args: Opener())
    instance = probe.Probe(tmp_path, "duffel_test_fixture", discard_book_reply=True)
    with pytest.raises(SystemExit, match="outcome_unknown"):
        instance.request("book", "POST", "/air/orders", {})
    assert not (instance.private / "book-response.json").exists()
    assert json.loads((tmp_path / "book-result.json").read_text())["outcome"] == "unknown"
    restarted = probe.Probe(tmp_path, "duffel_test_fixture")
    def forbidden(*args, **kwargs): pytest.fail("restart must not make another request")
    monkeypatch.setattr(restarted, "request", forbidden)
    with pytest.raises(ValueError, match="prior_booking_attempt_reconcile_first"):
        restarted.run("book")


@pytest.mark.parametrize("fault", ["empty", "duplicate", "more_pages", "foreign", "changed_amount", "live"])
def test_recovery_rejects_ambiguous_or_unbound_results(tmp_path, fault):
    instance = probe.Probe(tmp_path, "duffel_test_fixture")
    instance.state["selected_offer"] = {"total_amount": "100.00", "total_currency": "USD"}
    (instance.private / "book-request.json").write_text("{}")
    order = {"id": "ord_fixture", "live_mode": False, "total_amount": "100.00", "total_currency": "USD",
             "metadata": {"trustbound_reference": instance.state["reference"]}}
    records = [order]
    if fault == "empty": records = []
    if fault == "duplicate": records = [order, order]
    if fault == "foreign": order["metadata"]["trustbound_reference"] = "other"
    if fault == "changed_amount": order["total_amount"] = "101.00"
    if fault == "live": order["live_mode"] = True
    (tmp_path / "lookup-by-offer-result.json").write_text(json.dumps({"http_status": 200, "has_more": fault == "more_pages"}))
    (instance.private / "lookup-by-offer-response.json").write_text(json.dumps({"data": records}))
    with pytest.raises(ValueError, match="recovery_"):
        instance.run("recover")
    assert not (instance.private / "recovered-order.json").exists()


def test_changed_quote_stops_before_dispatch(tmp_path, monkeypatch):
    from datetime import datetime, timezone, timedelta
    instance = probe.Probe(tmp_path, "duffel_test_fixture")
    offer = {"id": "off_fixture", "live_mode": False,
             "owner": {"name": "Duffel Airways", "iata_code": "ZZ"},
             "total_currency": "USD", "total_amount": "101.00",
             "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    instance.state["selected_offer"] = {**offer, "total_amount": "100.00"}
    monkeypatch.setattr(instance, "previous", lambda stage: offer)
    monkeypatch.setattr(instance, "request", lambda *args: pytest.fail("changed quote dispatched"))
    with pytest.raises(ValueError, match="quote_changed_stop"):
        instance.run("book")
    assert not (instance.private / "flight.db").exists()


@pytest.mark.parametrize("meta", [None, {}, {"after": ""}])
def test_inventory_requires_explicit_pagination_evidence(tmp_path, monkeypatch, meta):
    import sys
    monkeypatch.setitem(sys.modules, "validate_duffel_sandbox", probe)
    audit_spec = importlib.util.spec_from_file_location(
        "failure_audit", Path(__file__).parents[1] / "scripts" / "duffel_failure_audit.py")
    audit = importlib.util.module_from_spec(audit_spec)
    audit_spec.loader.exec_module(audit)
    instance = probe.Probe(tmp_path, "duffel_test_fixture")
    def response(stage, *args):
        (instance.private / (stage + "-response.json")).write_text(json.dumps({"data": [], "meta": meta}))
        return []
    monkeypatch.setattr(instance, "request", response)
    with pytest.raises(ValueError, match="pagination_"):
        audit.inventory(instance, "inventory")
    assert not (tmp_path / "inventory.json").exists()
