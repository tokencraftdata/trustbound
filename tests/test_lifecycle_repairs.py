"""Local fault injection only. No provider requests or payment effects."""
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor, verify_statement


def setup_pair(tmp_path, allocation=100):
    p = FencedProcessor("p", tmp_path / "p.db")
    p.open_epoch("e")
    c = PersistentCoordinator("flight", allocation, tmp_path / "f.db")
    c.reserve_quote("q", 1, 100)
    return p, c


def test_release_cannot_reverse_behind_signed_closure(tmp_path):
    p, c = setup_pair(tmp_path)
    c.submit(p, "e", "q", 1, "pay")
    p.reconcile("pay", "released", "simulator-canceled")
    certificate = p.close_epoch("e")
    with pytest.raises(RuntimeError, match="terminal_payment_conflict"):
        p.reconcile("pay", "confirmed", "late-debit")
    assert verify_statement(certificate, p.public_key).liability_minor == 0
    assert p._connection.execute("SELECT status FROM payment").fetchone()[0] == "released"


def test_signing_key_and_old_certificate_survive_restart(tmp_path):
    p, _ = setup_pair(tmp_path)
    cert = p.close_epoch("e")
    key = p.public_key
    p.close()
    p = FencedProcessor("p", tmp_path / "p.db")
    assert p.public_key == key
    assert verify_statement(cert, p.public_key).valid
    p.close()
    with pytest.raises(RuntimeError, match="processor_identity_mismatch"):
        FencedProcessor("other", tmp_path / "p.db")


def test_legacy_processor_does_not_silently_replace_missing_key(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE epoch(epoch_id TEXT PRIMARY KEY, state TEXT, previous_root TEXT)")
        db.execute("INSERT INTO epoch VALUES ('e', 'closed', NULL)")
    with pytest.raises(RuntimeError, match="requires_migration"):
        FencedProcessor("p", path)


def test_duplicate_distinct_submission_rejected_and_exact_retry_idempotent(tmp_path):
    p, c = setup_pair(tmp_path)
    assert c.submit(p, "e", "q", 1, "pay") == 1
    assert c.submit(p, "e", "q", 1, "pay") == 1
    with pytest.raises(RuntimeError, match="submission_conflict"):
        c.submit(p, "e", "q", 1, "pay-again")
    assert p._connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0] == 1
    assert c.snapshot()["liability_minor"] == 100


@pytest.mark.parametrize("admitted", [False, True])
def test_timeout_before_or_after_admission_restart_retry(tmp_path, monkeypatch, admitted):
    p, c = setup_pair(tmp_path)
    original = p.admit

    def lost_response(*args):
        if admitted:
            original(*args)
        raise TimeoutError("simulated lost response")

    monkeypatch.setattr(p, "admit", lost_response)
    with pytest.raises(TimeoutError):
        c.submit(p, "e", "q", 1, "pay")
    assert c.snapshot()["quotes"][0][3] == "uncertain"
    assert c.snapshot()["liability_minor"] == 100
    c.close()
    p.close()
    p = FencedProcessor("p", tmp_path / "p.db")
    c = PersistentCoordinator("flight", 100, tmp_path / "f.db")
    assert c.submit(p, "e", "q", 1, "pay") == 1
    assert p._connection.execute("SELECT COUNT(*) FROM payment").fetchone()[0] == 1


def test_quote_revision_retains_submitted_exposure(tmp_path):
    p, c = setup_pair(tmp_path, 250)
    c.submit(p, "e", "q", 1, "pay")
    c.reserve_quote("q", 2, 150)
    assert c.snapshot()["liability_minor"] == 250
    assert c.snapshot()["quotes"][0][3] == "uncertain"
    with pytest.raises(RuntimeError, match="allocation_exceeded"):
        c.reserve_quote("q", 3, 151)
    assert c.snapshot()["liability_minor"] == 250


def test_exact_admission_replay_after_fence_does_not_create_work(tmp_path):
    p, c = setup_pair(tmp_path)
    c.submit(p, "e", "q", 1, "pay")
    p.close_epoch("e")
    assert c.submit(p, "e", "q", 1, "pay") == 1
    with pytest.raises(RuntimeError, match="epoch_closed_or_unknown"):
        p.admit("e", "new", "flight", 1, 1)
    with pytest.raises(RuntimeError, match="payment_id_conflict"):
        p.admit("e", "pay", "flight", 101, 1)


@pytest.mark.parametrize("terminal", ["released", "confirmed"])
def test_terminal_receipts_are_immutable_and_idempotent(tmp_path, terminal):
    p, c = setup_pair(tmp_path)
    c.submit(p, "e", "q", 1, "pay")
    p.reconcile("pay", terminal, "simulated-reference")
    p.reconcile("pay", terminal, "simulated-reference")
    c.apply_receipt("pay", terminal)
    c.apply_receipt("pay", terminal)
    for status in {"uncertain", "released", "confirmed"} - {terminal}:
        with pytest.raises(RuntimeError, match="terminal_payment_conflict"):
            p.reconcile("pay", status, "simulated-reference")
        with pytest.raises(RuntimeError, match="terminal_receipt_conflict"):
            c.apply_receipt("pay", status)


def test_uncertain_closed_certificate_stays_conservative_after_late_success(tmp_path):
    p, c = setup_pair(tmp_path)
    c.submit(p, "e", "q", 1, "pay")
    cert = p.close_epoch("e")
    p.reconcile("pay", "confirmed", "late-success")
    assert verify_statement(cert, p.public_key).liability_minor == 100


def test_retry_cannot_change_epoch_or_processor(tmp_path):
    p, c = setup_pair(tmp_path)
    c.submit(p, "e", "q", 1, "pay")
    p.open_epoch("other")
    with pytest.raises(RuntimeError, match="submission_conflict"):
        c.submit(p, "other", "q", 1, "pay")
    replacement = FencedProcessor("p", tmp_path / "replacement.db")
    replacement.open_epoch("e")
    with pytest.raises(RuntimeError, match="submission_conflict"):
        c.submit(replacement, "e", "q", 1, "pay")


def test_revocation_blocks_even_unadmitted_retry_without_freeing_liability(tmp_path, monkeypatch):
    p, c = setup_pair(tmp_path)
    def timeout(*args):
        raise TimeoutError()
    monkeypatch.setattr(p, "admit", timeout)
    with pytest.raises(TimeoutError):
        c.submit(p, "e", "q", 1, "pay")
    c.revoke()
    with pytest.raises(RuntimeError, match="authorization_revoked"):
        c.submit(p, "e", "q", 1, "pay")
    assert c.snapshot()["liability_minor"] == 100


def test_independent_database_connections_serialize_duplicate_claims(tmp_path):
    p, c = setup_pair(tmp_path)
    c.close()
    p.close()
    def attempt(payment):
        proc = FencedProcessor("p", tmp_path / "p.db")
        coord = PersistentCoordinator("flight", 100, tmp_path / "f.db")
        try:
            return coord.submit(proc, "e", "q", 1, payment)
        except RuntimeError as exc:
            return str(exc)
        finally:
            coord.close()
            proc.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["one", "two"]))
    assert sorted(map(str, results)) == ["1", "submission_conflict"]


@pytest.mark.parametrize("version,amount", [(0, 100), (1, -1), (True, 100), (1, True)])
def test_invalid_quotes_rejected(tmp_path, version, amount):
    _, c = setup_pair(tmp_path)
    with pytest.raises(ValueError, match="invalid_quote"):
        c.reserve_quote("new", version, amount)


def test_stale_revision_and_allocation_rebinding_rejected(tmp_path):
    _, c = setup_pair(tmp_path)
    with pytest.raises(RuntimeError, match="quote_version_not_increasing"):
        c.reserve_quote("q", 1, 1)
    c.close()
    with pytest.raises(RuntimeError, match="identity_or_allocation_mismatch"):
        PersistentCoordinator("flight", 101, tmp_path / "f.db")


def test_two_leg_partial_failure_retains_uncertain_leg(tmp_path, monkeypatch):
    p, flight = setup_pair(tmp_path)
    hotel = PersistentCoordinator("hotel", 100, tmp_path / "hotel.db")
    hotel.reserve_quote("h", 1, 100)
    flight.submit(p, "e", "q", 1, "flight")
    p.reconcile("flight", "confirmed", "sim-flight")
    flight.apply_receipt("flight", "confirmed")
    original = p.admit
    def delayed(*args):
        original(*args)
        raise TimeoutError("simulated hotel lost response")
    monkeypatch.setattr(p, "admit", delayed)
    with pytest.raises(TimeoutError):
        hotel.submit(p, "e", "h", 1, "hotel")
    assert flight.snapshot()["liability_minor"] + hotel.snapshot()["liability_minor"] == 200
    cert = p.close_epoch("e")
    assert verify_statement(cert, p.public_key).liability_minor == 200


def test_four_defect_audit_reports_no_reproduction():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "audit", Path(__file__).parents[1] / "scripts" / "audit_prototype.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run()
    assert result["released_then_confirmed_leaves_valid_zero_certificate"] is False
    assert result["processor_signing_identity_changes_on_restart"] is False
    assert result["two_submissions_from_one_reservation"] is False
    assert result["submitted_quote_revision_releases_old_reservation"] is False
