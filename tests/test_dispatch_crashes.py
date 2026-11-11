import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from trustbound.stripe_gate import StripeGate
from dispatch_crash_worker import LocalProvider, row


POINTS = ["register_before_commit", "register_after_commit", "grant_before_commit", "grant_after_commit",
          "fence_before_commit", "fence_after_commit", "claim_before_commit", "claim_after_commit",
          "send_before_provider_commit", "send_after_provider_commit", "after_reply",
          "observation_before_commit", "observation_after_commit",
          "conflict_before_commit", "conflict_after_commit"]


def effects(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0]


@pytest.mark.parametrize("point", POINTS)
def test_sigkill_boundary(tmp_path, point):
    database, provider = tmp_path / "gate.db", tmp_path / "provider.db"
    with sqlite3.connect(provider) as connection:
        connection.execute("CREATE TABLE effects(path TEXT, idem TEXT)")
    gate = StripeGate(database, "crash-epoch")
    if not point.startswith("register_"):
        gate.register(row())
    if point.startswith(("claim_", "send_", "observation_")) or point == "after_reply":
        gate.grant("pi_Crash1", "capture")
        gate.fence()
    if point.startswith("conflict_"):
        gate.observe(row("canceled"))
        gate.fence()
    gate.close()
    child = subprocess.run([sys.executable, str(Path(__file__).with_name("dispatch_crash_worker.py")),
                            str(tmp_path), point], capture_output=True, timeout=20)
    assert child.returncode == -signal.SIGKILL, child.stderr.decode()
    gate = StripeGate(database, "crash-epoch")
    assert gate.db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    if point.startswith("register_"):
        assert len(gate.snapshot()["records"]) == int(point.endswith("after_commit"))
    elif point.startswith("grant_"):
        assert gate.db.execute("SELECT COUNT(*) FROM command").fetchone()[0] == int(point.endswith("after_commit"))
    elif point.startswith("fence_"):
        assert gate.snapshot()["closed"] == point.endswith("after_commit")
    elif point.startswith("conflict_"):
        snapshot = gate.snapshot()
        committed = point.endswith("after_commit")
        assert snapshot["has_contract_conflicts"] == committed
        assert snapshot["known_manifest_resolved"] == (not committed)
        assert snapshot["retained_minor"] == (200 if committed else 0)
    else:
        expected_effects = int(point in {"send_after_provider_commit", "after_reply",
                                         "observation_before_commit", "observation_after_commit"})
        assert effects(provider) == expected_effects
        if point == "claim_before_commit":
            # Rollback permits a first dispatch; no previous send occurred.
            gate.dispatch(1, LocalProvider(provider))
            assert effects(provider) == 1
        else:
            with pytest.raises(RuntimeError, match="already_claimed"):
                gate.dispatch(1, LocalProvider(provider))
            assert effects(provider) == expected_effects
        snapshot = gate.snapshot()
        assert snapshot["known_manifest_resolved"] == (point == "observation_after_commit")
        assert snapshot["retained_minor"] == 200
    assert effects(provider) <= 1
    gate.close()


def test_two_workers_race_one_command(tmp_path):
    database, provider = tmp_path / "gate.db", tmp_path / "provider.db"
    with sqlite3.connect(provider) as connection:
        connection.execute("CREATE TABLE effects(path TEXT, idem TEXT)")
    gate = StripeGate(database, "crash-epoch")
    gate.register(row())
    gate.grant("pi_Crash1", "capture")
    gate.close()
    barrier = Barrier(2)
    def dispatch():
        connection = StripeGate(database, "crash-epoch")
        barrier.wait(timeout=5)
        try:
            return connection.dispatch(1, LocalProvider(provider))["http_status"]
        except RuntimeError as exc:
            return str(exc)
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: dispatch(), range(2)))
    assert sorted(map(str, outcomes)) == ["200", "command_unknown_or_already_claimed"]
    assert effects(provider) == 1


def test_competing_initial_epoch_identities(tmp_path):
    database = tmp_path / "gate.db"
    barrier = Barrier(2)
    def initialize(epoch):
        barrier.wait(timeout=5)
        try:
            gate = StripeGate(database, epoch)
            gate.close()
            return True
        except ValueError as exc:
            assert str(exc) == "epoch_identity_mismatch"
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(initialize, ["epoch-a", "epoch-b"]))
    assert sorted(results) == [False, True]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM epoch").fetchone() == (1,)


def test_timeout_retains_claim_and_never_exports_reply_secrets(tmp_path):
    gate = StripeGate(tmp_path / "gate.db", "epoch")
    gate.register(row())
    command = gate.grant("pi_Crash1", "confirm")
    class TimeoutTransport:
        calls = 0
        def request(self, *args):
            self.calls += 1
            raise TimeoutError()
    transport = TimeoutTransport()
    with pytest.raises(TimeoutError):
        gate.dispatch(command, transport)
    with pytest.raises(RuntimeError, match="already_claimed"):
        gate.dispatch(command, transport)
    assert transport.calls == 1 and gate.snapshot()["retained_minor"] == 200
    gate.close()
