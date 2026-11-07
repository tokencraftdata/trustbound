import sqlite3

from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor


def test_flight_and_hotel_use_separate_persistent_databases(tmp_path):
    flight = PersistentCoordinator("flight", 700, tmp_path / "flight.db")
    hotel = PersistentCoordinator("hotel", 500, tmp_path / "hotel.db")
    flight.reserve_quote("qf", 1, 600)
    hotel.reserve_quote("qh", 1, 400)
    flight.close()
    hotel.close()
    assert (tmp_path / "flight.db").read_bytes() != (tmp_path / "hotel.db").read_bytes()
    assert sqlite3.connect(tmp_path / "flight.db").execute("SELECT COUNT(*) FROM quote").fetchone()[0] == 1
    assert sqlite3.connect(tmp_path / "hotel.db").execute("SELECT COUNT(*) FROM quote").fetchone()[0] == 1


def test_quote_revision_atomically_releases_old_reservation(tmp_path):
    coordinator = PersistentCoordinator("flight", 1_000, tmp_path / "flight.db")
    coordinator.reserve_quote("q", 1, 900)
    coordinator.reserve_quote("q", 2, 950)
    snapshot = coordinator.snapshot()
    assert snapshot["liability_minor"] == 950
    assert snapshot["quotes"][0][3] == "released"
    assert snapshot["quotes"][1][3] == "reserved"


def test_quote_revision_above_allocation_preserves_old_reservation(tmp_path):
    coordinator = PersistentCoordinator("flight", 1_000, tmp_path / "flight.db")
    coordinator.reserve_quote("q", 1, 900)
    try:
        coordinator.reserve_quote("q", 2, 1_100)
        assert False, "over-allocation revision accepted"
    except RuntimeError:
        pass
    snapshot = coordinator.snapshot()
    assert snapshot["liability_minor"] == 900
    assert len(snapshot["quotes"]) == 1


def test_revocation_fences_new_quotes_but_keeps_uncertain_liability(tmp_path):
    coordinator = PersistentCoordinator("flight", 1_000, tmp_path / "flight.db")
    processor = FencedProcessor("processor", tmp_path / "processor.db")
    processor.open_epoch("e1")
    coordinator.reserve_quote("q", 1, 700)
    coordinator.submit(processor, "e1", "q", 1, "p1")
    coordinator.apply_receipt("p1", "uncertain")
    coordinator.revoke()
    assert coordinator.snapshot()["liability_minor"] == 700
    try:
        coordinator.reserve_quote("new", 1, 10)
        assert False, "revoked coordinator admitted new work"
    except RuntimeError as exc:
        assert str(exc) == "authorization_revoked"


def test_confirmed_receipt_after_revocation_remains_accounted(tmp_path):
    coordinator = PersistentCoordinator("hotel", 1_000, tmp_path / "hotel.db")
    processor = FencedProcessor("processor", tmp_path / "processor.db")
    processor.open_epoch("e1")
    coordinator.reserve_quote("q", 1, 700)
    coordinator.submit(processor, "e1", "q", 1, "p1")
    coordinator.revoke()
    coordinator.apply_receipt("p1", "confirmed")
    assert coordinator.snapshot()["liability_minor"] == 700
