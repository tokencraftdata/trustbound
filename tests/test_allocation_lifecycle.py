from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import sqlite3
from threading import Barrier

import pytest

from trustbound.allocation import AllocationAuthority, verify_allocation, verify_allocation_signature


@pytest.mark.parametrize("amount", [-1, True, 1.5, "10", 2**63])
def test_invalid_caps_do_not_change_available_capacity(tmp_path, amount):
    authority = AllocationAuthority(tmp_path / "allocation.db")
    try:
        authority.create_trip("trip", 1000, "USD")
        with pytest.raises(ValueError):
            authority.issue("trip", "flight", amount)
        right = authority.issue("trip", "hotel", 1000)
        assert right.cap_minor == 1000
    finally:
        authority.close()


@pytest.mark.parametrize("budget", [-1, True, 1.5, "1000", 2**63])
def test_invalid_trip_budget_is_rejected(tmp_path, budget):
    authority = AllocationAuthority(tmp_path / "allocation.db")
    try:
        with pytest.raises(ValueError):
            authority.create_trip("trip", budget, "USD")
        authority.create_trip("trip", 1000, "USD")
    finally:
        authority.close()


@pytest.mark.parametrize("ttl", [0, -1, True, 0.5, "10", 2**63])
def test_invalid_lifetime_does_not_reserve_capacity(tmp_path, ttl):
    authority = AllocationAuthority(tmp_path / "allocation.db")
    try:
        authority.create_trip("trip", 1000, "USD")
        with pytest.raises(ValueError):
            authority.issue("trip", "flight", 1000, ttl_seconds=ttl)
        assert authority.issue("trip", "hotel", 1000).cap_minor == 1000
    finally:
        authority.close()


def test_retired_token_is_not_live_authority(tmp_path):
    authority = AllocationAuthority(tmp_path / "allocation.db")
    try:
        authority.create_trip("trip", 1000, "USD")
        old = authority.issue("trip", "flight", 600)
        assert verify_allocation(old, authority.public_key, "flight", authority=authority)
        assert not verify_allocation(old, authority.public_key, "flight")
        authority.retire(old.right_id)
        assert not verify_allocation(old, authority.public_key, "flight")
        assert not verify_allocation(old, authority.public_key, "flight", authority=authority)
        assert verify_allocation_signature(old, authority.public_key, "flight")
        with pytest.raises(RuntimeError, match="allocation_not_available"):
            authority.claim(old, "flight")
        replacement = authority.issue("trip", "hotel", 900)
        assert authority.claim(replacement, "hotel") == replacement
    finally:
        authority.close()


def test_claimed_capacity_survives_retirement_expiry_and_restart(tmp_path, monkeypatch):
    path = tmp_path / "allocation.db"
    authority = AllocationAuthority(path)
    authority.create_trip("trip", 1000, "USD")
    right = authority.issue("trip", "flight", 600)
    key = authority.public_key
    authority.claim(right, "flight")
    authority.retire(right.right_id)
    authority.close()
    monkeypatch.setattr("trustbound.allocation.time.time", lambda: right.expires_at + 1)
    reopened = AllocationAuthority(path)
    try:
        assert reopened.public_key == key
        with pytest.raises(RuntimeError, match="allocation_not_available"):
            reopened.claim(right, "flight")
        with pytest.raises(RuntimeError, match="overallocated"):
            reopened.issue("trip", "hotel", 401)
        assert reopened.issue("trip", "hotel", 400).cap_minor == 400
    finally:
        reopened.close()


def test_unclaimed_token_survives_restart_but_cannot_be_claimed_twice(tmp_path):
    path = tmp_path / "allocation.db"
    authority = AllocationAuthority(path)
    authority.create_trip("trip", 1000, "USD")
    right = authority.issue("trip", "flight", 600)
    authority.close()
    reopened = AllocationAuthority(path)
    try:
        assert reopened.claim(right, "flight") == right
        assert not verify_allocation(right, reopened.public_key, "flight", authority=reopened)
        with pytest.raises(RuntimeError, match="allocation_not_available"):
            reopened.claim(right, "flight")
    finally:
        reopened.close()


def test_concurrent_claims_admit_only_one_coordinator(tmp_path):
    path = tmp_path / "allocation.db"
    authority = AllocationAuthority(path)
    authority.create_trip("trip", 1000, "USD")
    right = authority.issue("trip", "flight", 600)
    authority.close()
    barrier = Barrier(2)

    def claim():
        connection = AllocationAuthority(path)
        try:
            barrier.wait(timeout=5)
            connection.claim(right, "flight")
            return "claimed"
        except RuntimeError as exc:
            return str(exc)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        assert sorted(future.result() for future in futures) == ["allocation_not_available", "claimed"]


def test_retirement_racing_claim_cannot_create_reusable_capacity(tmp_path):
    path = tmp_path / "allocation.db"
    authority = AllocationAuthority(path)
    authority.create_trip("trip", 1000, "USD")
    right = authority.issue("trip", "flight", 600)
    barrier = Barrier(2)

    def operation(claim):
        connection = AllocationAuthority(path)
        try:
            barrier.wait(timeout=5)
            if claim:
                connection.claim(right, "flight")
                return True
            connection.retire(right.right_id)
            return False
        except RuntimeError as exc:
            assert str(exc) == "allocation_not_available"
            return False
        finally:
            connection.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            claim = pool.submit(operation, True)
            retirement = pool.submit(operation, False)
            claimed = claim.result()
            retirement.result()
        if claimed:
            with pytest.raises(RuntimeError, match="overallocated"):
                authority.issue("trip", "hotel", 900)
        else:
            assert authority.issue("trip", "hotel", 900).cap_minor == 900
    finally:
        authority.close()


def test_legacy_database_requires_explicit_migration(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE allocation(right_id TEXT PRIMARY KEY, active INTEGER)")
        connection.execute("INSERT INTO allocation VALUES ('old-right', 0)")
    with pytest.raises(RuntimeError, match="legacy_allocation_requires_migration"):
        AllocationAuthority(path)


def test_missing_signing_key_cannot_be_silently_replaced(tmp_path):
    path = tmp_path / "allocation.db"
    authority = AllocationAuthority(path)
    authority.create_trip("trip", 1000, "USD")
    authority.issue("trip", "flight", 600)
    authority.close()
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM allocation_signing_identity")
    with pytest.raises(RuntimeError, match="allocation_identity_requires_migration"):
        AllocationAuthority(path)


def test_tampered_or_wrong_coordinator_claim_does_not_consume_right(tmp_path):
    authority = AllocationAuthority(tmp_path / "allocation.db")
    try:
        authority.create_trip("trip", 1000, "USD")
        right = authority.issue("trip", "flight", 600)
        for candidate, coordinator in ((replace(right, cap_minor=900), "flight"), (right, "hotel")):
            with pytest.raises(RuntimeError, match="allocation_not_available"):
                authority.claim(candidate, coordinator)
        assert authority.claim(right, "flight") == right
    finally:
        authority.close()
