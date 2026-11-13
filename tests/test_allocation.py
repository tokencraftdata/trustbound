from dataclasses import replace

from trustbound.allocation import AllocationAuthority, verify_allocation


def test_signed_allocations_are_non_overlapping_caps(tmp_path):
    authority = AllocationAuthority(tmp_path / "authority.db")
    authority.create_trip("trip", 1_000, "USD")
    flight = authority.issue("trip", "flight", 600)
    hotel = authority.issue("trip", "hotel", 400)
    assert verify_allocation(flight, authority.public_key, "flight", authority=authority)
    assert verify_allocation(hotel, authority.public_key, "hotel", authority=authority)
    try:
        authority.issue("trip", "car", 1)
        assert False, "over-allocation was accepted"
    except RuntimeError as exc:
        assert str(exc) == "trip_budget_overallocated"


def test_allocation_tampering_is_detected(tmp_path):
    authority = AllocationAuthority(tmp_path / "authority.db")
    authority.create_trip("trip", 1_000, "USD")
    right = authority.issue("trip", "flight", 600)
    assert not verify_allocation(replace(right, cap_minor=900), authority.public_key, "flight", authority=authority)


def test_allocation_can_be_retired_before_reallocation(tmp_path):
    authority = AllocationAuthority(tmp_path / "authority.db")
    authority.create_trip("trip", 1_000, "USD")
    flight = authority.issue("trip", "flight", 600)
    authority.retire(flight.right_id)
    replacement = authority.issue("trip", "hotel", 900)
    assert replacement.generation == 1


def test_expired_allocation_is_rejected(tmp_path):
    authority = AllocationAuthority(tmp_path / "authority.db")
    authority.create_trip("trip", 1_000, "USD")
    right = authority.issue("trip", "flight", 600, ttl_seconds=1)
    assert not verify_allocation(
        right, authority.public_key, "flight", now=right.expires_at, authority=authority
    )
