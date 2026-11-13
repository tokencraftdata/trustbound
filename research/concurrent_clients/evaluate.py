"""Bounded concurrent-worker experiments, including serialized provider reconciliation.

Workers have separate SQLite connections and call the real command interface.
The bundled socket listener remains serial. This harness does not prove general
linearizability, process isolation, power-loss durability, or provider contracts.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import hashlib
import itertools
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from research.support import require, write_report
from trustbound.credential_service import CommandService
from trustbound.stripe_gate import StripeGate

EPOCH = "concurrent-epoch"
TIMEOUT = 15


def wait(event):
    require(event.wait(TIMEOUT), "coordination timeout")


def observation(identity, amount, status):
    return {"id": identity, "object": "payment_intent", "livemode": False,
            "amount": amount, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": status,
            "amount_received": amount if status == "succeeded" else 0,
            "amount_capturable": amount if status == "requires_capture" else 0}


class Trace:
    def __init__(self, path):
        self.path = path
        self.events = []
        self.lock = threading.Lock()

    def add(self, actor, action, **fields):
        with self.lock:
            number = len(self.events)
            self.events.append({"sequence": number, "actor": actor, "action": action, **fields})
            with self.path.open("a") as stream:
                stream.write(json.dumps(self.events[-1]) + "\n")
            return number


class Provider:
    """One durable multi-identity source, with atomic irreversible outcomes.

    Each method opens its own connection. No deduplication hides extra capture
    invocations; every call is recorded even if its identity is already terminal.
    Effects have no uniqueness constraint. Source terminality is a simulator rule.
    """
    def __init__(self, path, amounts, trace, fault="normal", before_capture=None, after_read=None):
        self.path, self.amounts, self.trace = path, amounts, trace
        self.fault, self.before_capture, self.after_read = fault, before_capture, after_read

    def initialize(self):
        with closing(sqlite3.connect(self.path, timeout=TIMEOUT)) as db, db:
            db.executescript("""
                CREATE TABLE payment(id TEXT PRIMARY KEY, amount INTEGER, status TEXT);
                CREATE TABLE calls(identity TEXT, action TEXT);
                CREATE TABLE effects(identity TEXT);
            """)
            db.executemany("INSERT INTO payment VALUES (?, ?, 'requires_payment_method')",
                           self.amounts.items())

    def retrieve(self, identity):
        with closing(sqlite3.connect(self.path, timeout=TIMEOUT)) as db:
            amount, status = db.execute("SELECT amount,status FROM payment WHERE id=?", (identity,)).fetchone()
        row = observation(identity, amount, status)
        self.trace.add("provider", "retrieve", identity=identity, status=status)
        if self.after_read:
            self.after_read(identity, row)
        return row

    def request(self, method, path, body, idem):
        prefix, identity, action = path.rsplit("/", 2)
        require(prefix == "/v1/payment_intents" and method == "POST", "wrong transport target")
        require(identity in self.amounts and action in {"confirm", "capture"}, "wrong transport scope")
        require(body == ({"payment_method": "pm_card_visa"} if action == "confirm" else {}), "wrong body")
        require(idem.startswith(EPOCH + ":dispatch:") and idem.rsplit(":", 1)[1].isdigit(), "wrong command key")
        self.trace.add("provider", "invocation", identity=identity, operation=action, idempotency_key=idem)
        if action == "capture" and self.before_capture:
            self.before_capture(identity)
        paid = False
        pending = action == "capture" and self.fault == "pending_last" and identity == max(self.amounts)
        with closing(sqlite3.connect(self.path, timeout=TIMEOUT)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT INTO calls VALUES (?,?)", (identity, action))
            status = db.execute("SELECT status FROM payment WHERE id=?", (identity,)).fetchone()[0]
            code = 400
            if action == "confirm" and status == "requires_payment_method":
                status, code = "requires_capture", 200
            elif action == "capture" and status == "requires_capture" and not pending:
                status, code, paid = "succeeded", 200, True
                db.execute("INSERT INTO effects VALUES (?)", (identity,))
            db.execute("UPDATE payment SET status=? WHERE id=?", (status, identity))
        self.trace.add("provider", "commit", identity=identity, operation=action, status=status)
        if pending or (paid and self.fault == "lost_reply"):
            raise TimeoutError("injected provider timeout")
        return code, observation(identity, self.amounts[identity], status)

    def cancel(self, identity):
        with closing(sqlite3.connect(self.path, timeout=TIMEOUT)) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE payment SET status='canceled' WHERE id=? AND status IN ('requires_payment_method','requires_capture')", (identity,))
        self.trace.add("operator", "cancel", identity=identity)

    def state(self):
        with closing(sqlite3.connect(self.path, timeout=TIMEOUT)) as db:
            return {"statuses": dict(db.execute("SELECT id,status FROM payment ORDER BY id")),
                    "captures": [r[0] for r in db.execute("SELECT identity FROM calls WHERE action='capture' ORDER BY rowid")],
                    "effects": [r[0] for r in db.execute("SELECT identity FROM effects ORDER BY rowid")]}


class Experiment:
    def __init__(self, directory, payments=2, fault="normal", gate_type=StripeGate, ungranted_last=False):
        self.path = Path(directory) / "gate.db"
        self.trace = Trace(Path(directory) / "history.jsonl")
        self.amounts = {f"pi_Concurrent{i}": i * 100 for i in range(1, payments + 1)}
        self.provider = Provider(Path(directory) / "provider.db", self.amounts, self.trace, fault)
        self.provider.initialize()
        self.gate_type = gate_type
        self.commands = {}
        self.expected_commands = []
        with closing(StripeGate(self.path, EPOCH)) as gate:
            for identity in self.amounts:
                gate.register(self.provider.retrieve(identity))
                confirm = gate.grant(identity, "confirm")
                gate.dispatch(confirm, self.provider)
                self.expected_commands.append({"id": confirm, "payment_id": identity,
                                               "action": "confirm", "claimed": 1})
                if not ungranted_last or identity != max(self.amounts):
                    self.commands[identity] = gate.grant(identity, "capture")
                    self.expected_commands.append({"id": self.commands[identity], "payment_id": identity,
                                                   "action": "capture", "claimed": 0})

    def request(self, gate, actor, request, provider=None):
        start = self.trace.add(actor, "request", request=request)
        reply = CommandService(gate, provider or self.provider).handle(json.dumps(request).encode())
        self.trace.add(actor, "reply", request_sequence=start, response=reply)
        return reply

    def dispatch(self, gate, actor, identity):
        return self.request(gate, actor, {"op": "dispatch", "command_id": self.commands[identity]})

    def reconcile(self):
        with closing(self.gate_type(self.path, EPOCH)) as gate:
            reply = self.request(gate, "operator", {"op": "reconcile"})
            require(reply["ok"], "quiescent reconciliation rejected")

    def checkpoint(self, statuses, *, captures, journal=None, conflict=None):
        """Check scenario-derived expectations at a quiescent/synchronized cut.

        Expected statuses, capture identities and journal membership are supplied
        by the scenario, not inferred from implementation snapshots.
        """
        journal = set(self.amounts) if journal is None else set(journal)
        with closing(self.gate_type(self.path, EPOCH)) as gate:
            snapshot = gate.snapshot()
        source = self.provider.state()
        require(source["statuses"] == statuses, "provider state differs from scenario")
        require(sorted(source["captures"]) == sorted(captures), "extra or missing capture invocation")
        paid = {i for i, status in statuses.items() if status == "succeeded"}
        rights = {i for i, status in statuses.items() if status == "requires_capture"}
        require(sorted(source["effects"]) == sorted(paid), "extra or missing payment effect")
        records = {r["id"]: r for r in snapshot["records"]}
        require(set(records) == journal, "journal membership differs from scenario")
        require(paid | rights <= journal, "effect or authority omitted from journal")
        require(snapshot["closed"], "admission fence missing")
        conflicts = [] if conflict is None else [{"payment_id": conflict, "reason": "terminal_observation_changed"}]
        require(snapshot["contract_conflicts"] == conflicts, "unexpected observation conflicts")
        for identity in journal:
            status = statuses[identity]
            expected = status if status in {"succeeded", "canceled"} else "uncertain"
            require(records[identity] == {"id": identity, "amount": self.amounts[identity],
                    "status": expected, "received": self.amounts[identity] if status == "succeeded" else 0,
                    "capturable": self.amounts[identity] if status == "requires_capture" else 0},
                    "record differs from scenario")
        resolved = not conflict and all(statuses[i] in {"succeeded", "canceled"} for i in journal)
        require(snapshot["known_manifest_resolved"] == bool(resolved), "premature or missing closure")
        retained = sum(self.amounts[i] for i in journal if statuses[i] != "canceled" or i == conflict)
        require(snapshot["retained_minor"] == retained, "reservation differs from scenario")
        expected_commands = [{**c, "claimed": 1 if c["action"] == "confirm" else int(c["payment_id"] in captures)}
                             for c in self.expected_commands]
        require(snapshot["commands"] == expected_commands, "command coverage or claims differ from scenario")
        self.trace.add("auditor", "checkpoint", snapshot=snapshot, provider=source)
        return {"resolved": bool(resolved), "paid_effects": len(paid), "outstanding_rights": len(rights),
                "capture_invocations": len(captures), "observation_conflicts": len(conflicts),
                "max_capture_invocations_per_identity": max((source["captures"].count(i) for i in journal), default=0),
                "max_paid_effects_per_identity": max((source["effects"].count(i) for i in journal), default=0)}


def contention(directory, clients, payments, fault, gate_type=StripeGate):
    experiment = Experiment(directory, payments, fault, gate_type)
    with closing(StripeGate(experiment.path, EPOCH)) as gate:
        gate.fence()
    barrier = threading.Barrier(clients, timeout=TIMEOUT)

    def worker(number):
        with closing(gate_type(experiment.path, EPOCH)) as gate:
            for identity in experiment.amounts:
                for attempt in range(2):
                    barrier.wait()
                    experiment.dispatch(gate, f"client-{number}", identity)
    with ThreadPoolExecutor(max_workers=clients) as pool:
        futures = [pool.submit(worker, i) for i in range(clients)]
        for future in futures:
            future.result(timeout=TIMEOUT * payments * 2)
    experiment.reconcile()
    statuses = {i: "requires_capture" if fault == "pending_last" and i == max(experiment.amounts)
                else "succeeded" for i in experiment.amounts}
    result = experiment.checkpoint(statuses, captures=list(experiment.amounts))
    return {"family": "contention", "clients": clients, "payments": payments, "fault": fault,
            **result, "history": experiment.trace.events}


def cancellation_race(directory, order, fault):
    experiment = Experiment(directory, fault=fault)
    flight, hotel = experiment.amounts
    entered, release = threading.Event(), threading.Event()

    def hold(identity):
        if identity == hotel:
            entered.set()
            wait(release)
    experiment.provider.before_capture = hold

    def worker():
        with closing(StripeGate(experiment.path, EPOCH)) as gate:
            return experiment.dispatch(gate, "hotel-client", hotel)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        try:
            wait(entered)
            with closing(StripeGate(experiment.path, EPOCH)) as gate:
                experiment.dispatch(gate, "flight-client", flight)
                gate.fence()
                experiment.trace.add("operator", "fence_during_hotel_dispatch")
                retry = experiment.dispatch(gate, "retry-client", hotel)
                require(not retry["ok"], "in-flight duplicate dispatch accepted")
                reply = experiment.request(gate, "poll-client", {"op": "reconcile"})
                require(reply["ok"] and not reply["result"]["known_manifest_resolved"],
                        "closed while hotel work was still pending")
            if order == "cancel_first":
                experiment.provider.cancel(hotel)
                experiment.reconcile()
                # A delayed local invocation is harmless only under source terminality.
                with closing(StripeGate(experiment.path, EPOCH)) as gate:
                    require(gate.snapshot()["known_manifest_resolved"], "terminal cancellation did not resolve")
            release.set()
            future.result(timeout=TIMEOUT)
            if order == "capture_first":
                experiment.provider.cancel(hotel)
        finally:
            release.set()
    experiment.reconcile()
    statuses = {flight: "succeeded", hotel: "canceled" if order == "cancel_first" else "succeeded"}
    result = experiment.checkpoint(statuses, captures=[flight, hotel])
    return {"family": "cancellation_race", "order": order, "fault": fault,
            **result, "history": experiment.trace.events}


class PausedTransactionGate(StripeGate):
    """Test instrumentation: pause after a transaction callback, before commit."""
    pause = None

    def _transaction(self, operation):
        def wrapped():
            result = operation()
            if self.pause:
                entered, release = self.pause
                entered.set()
                wait(release)
            return result
        return super()._transaction(wrapped)


def admission_race(directory, operation, winner):
    experiment = Experiment(directory, ungranted_last=True)
    target = max(experiment.amounts)
    if operation == "register":
        target = "pi_Concurrent3"
        experiment.amounts[target] = 300
        with closing(sqlite3.connect(experiment.provider.path)) as db, db:
            db.execute("INSERT INTO payment VALUES (?,300,'requires_payment_method')", (target,))
    entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
    ready = threading.Barrier(2, timeout=TIMEOUT)

    def worker(name):
        with closing(PausedTransactionGate(experiment.path, EPOCH)) as gate:
            ready.wait()
            if name == winner:
                gate.pause = entered, release
            else:
                wait(entered)
                attempted.set()
            experiment.trace.add(name, "begin_admission_operation", operation=operation if name == "admit" else "fence")
            try:
                if name == "fence":
                    gate.fence()
                elif operation == "register":
                    gate.register(observation(target, 300, "requires_payment_method"))
                else:
                    gate.grant(target, "capture")
                outcome = "accepted"
            except RuntimeError as exc:
                require(str(exc) == "epoch_fenced", "unexpected admission rejection")
                outcome = "fenced"
            experiment.trace.add(name, "end_admission_operation", outcome=outcome)
            return outcome
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {name: pool.submit(worker, name) for name in ("admit", "fence")}
        try:
            wait(entered)
            wait(attempted)
        finally:
            release.set()
        outcomes = {name: future.result(timeout=TIMEOUT) for name, future in futures.items()}
    require(outcomes == {"admit": "accepted" if winner == "admit" else "fenced", "fence": "accepted"},
            "admission/fence ordering differs from forced transaction order")
    if operation == "grant" and winner == "admit":
        experiment.expected_commands.append({"id": 4, "payment_id": target, "action": "capture", "claimed": 0})
    with closing(StripeGate(experiment.path, EPOCH)) as gate:
        before = gate.snapshot()
        for action in (lambda: gate.register(observation("pi_Late", 100, "requires_payment_method")),
                       lambda: gate.grant("pi_Concurrent1", "capture")):
            try:
                action()
            except RuntimeError as exc:
                require(str(exc) == "epoch_fenced", "late admission had unexpected rejection")
            else:
                raise ValueError("late admission succeeded")
        require(gate.snapshot() == before, "journal changed after fence")
        grants = [r for r in before["commands"] if r["payment_id"] == target and r["action"] == "capture"]
        require(len(grants) == int(operation == "grant" and winner == "admit"), "grant/fence coverage differs")
    statuses = {}
    for identity in experiment.amounts:
        experiment.provider.cancel(identity)
        statuses[identity] = "canceled"
    experiment.reconcile()
    journal = set(experiment.amounts)
    if operation == "register" and winner == "fence":
        journal.remove(target)
    result = experiment.checkpoint(statuses, captures=[], journal=journal)
    return {"family": "admission_race", "operation": operation, "winner": winner,
            **result, "history": experiment.trace.events}


def stale_reconciliation(directory, terminal, gate_type=StripeGate):
    """A delayed pending read must commit before a competing terminal read."""
    experiment = Experiment(directory, gate_type=gate_type)
    target = min(experiment.amounts)
    entered, release = threading.Event(), threading.Event()
    capture_entered, capture_release = threading.Event(), threading.Event()
    fresh_ready, fresh_start = threading.Event(), threading.Event()
    fresh_attempt, fresh_read = threading.Event(), threading.Event()
    with closing(gate_type(experiment.path, EPOCH)) as gate:
        gate.fence()
        if terminal == "succeeded":
            for identity in experiment.amounts:
                if identity != target:
                    require(experiment.dispatch(gate, "payment-client", identity)["ok"], "setup capture failed")

    def hold_capture(identity):
        require(identity == target, "unexpected paused capture")
        capture_entered.set()
        wait(capture_release)

    def hold_read(identity, row):
        if identity == target:
            require(row["status"] == "requires_capture", "delayed read not staged before completion")
            entered.set()
            wait(release)

    def mark_fresh_read(identity, row):
        if identity == target:
            fresh_read.set()

    delayed_provider = Provider(experiment.provider.path, experiment.amounts, experiment.trace, after_read=hold_read)
    fresh_provider = Provider(experiment.provider.path, experiment.amounts, experiment.trace, after_read=mark_fresh_read)
    capture_provider = Provider(experiment.provider.path, experiment.amounts, experiment.trace, before_capture=hold_capture)

    def capture_worker():
        with closing(gate_type(experiment.path, EPOCH)) as gate:
            return experiment.request(gate, "payment-client", {"op": "dispatch", "command_id": experiment.commands[target]}, capture_provider)

    def delayed_worker():
        with closing(gate_type(experiment.path, EPOCH)) as gate:
            return experiment.request(gate, "delayed-reconciler", {"op": "reconcile"}, delayed_provider)

    def fresh_worker():
        with closing(gate_type(experiment.path, EPOCH)) as gate:
            # Open the connection before the delayed read holds its transaction.
            fresh_ready.set()
            wait(fresh_start)
            gate.db.set_trace_callback(lambda sql: fresh_attempt.set() if sql == "BEGIN IMMEDIATE" else None)
            return experiment.request(gate, "fresh-reconciler", {"op": "reconcile"}, fresh_provider)

    with ThreadPoolExecutor(max_workers=3) as pool:
        fresh = pool.submit(fresh_worker)
        try:
            wait(fresh_ready)
            capture = None
            if terminal == "succeeded":
                capture = pool.submit(capture_worker)
                wait(capture_entered)
            delayed = pool.submit(delayed_worker)
            wait(entered)
            if terminal == "canceled":
                for identity in experiment.amounts:
                    experiment.provider.cancel(identity)
            else:
                capture_release.set()
                require(capture.result(timeout=TIMEOUT)["ok"], "in-flight capture failed")
            require(set(experiment.provider.state()["statuses"].values()) == {terminal}, "source not terminal")
            # A separate zero-wait connection proves that the journal write lock
            # covers the paused read; no scheduling delay is used as the oracle.
            locked = False
            with closing(sqlite3.connect(experiment.path, timeout=0)) as probe:
                try:
                    probe.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as exc:
                    if exc.sqlite_errorcode != sqlite3.SQLITE_BUSY:
                        raise
                    locked = True
                finally:
                    probe.rollback()
            require(locked, "provider read was not serialized with its journal update")
            fresh_start.set()
            wait(fresh_attempt)
            require(not fresh_read.is_set(), "competing retrieval overtook the delayed read")
            release.set()
            require(delayed.result(timeout=TIMEOUT)["ok"], "delayed reconciliation rejected")
            require(fresh.result(timeout=TIMEOUT)["ok"], "fresh reconciliation rejected")
        finally:
            release.set()
            capture_release.set()
            fresh_start.set()
    experiment.reconcile()
    statuses = dict.fromkeys(experiment.amounts, terminal)
    captures = list(experiment.amounts) if terminal == "succeeded" else []
    result = experiment.checkpoint(statuses, captures=captures)
    return {"family": "stale_reconciliation", "terminal": terminal,
            "conflict_free_reconciliation": True,
            "finding": "Serialized read/application prevents a competing terminal read from overtaking a delayed pending response.",
            **result, "history": experiment.trace.events}


def cases(repeats):
    for repetition in range(repeats):
        for clients, payments, fault in itertools.product((2, 4, 8), (2, 4), ("normal", "lost_reply", "pending_last")):
            yield contention, (clients, payments, fault), repetition
        for order, fault in itertools.product(("cancel_first", "capture_first"), ("normal", "lost_reply")):
            yield cancellation_race, (order, fault), repetition
        for operation, winner in itertools.product(("register", "grant"), ("admit", "fence")):
            yield admission_race, (operation, winner), repetition
        for terminal in ("succeeded", "canceled"):
            yield stale_reconciliation, (terminal,), repetition


def run_suite(repeats=3):
    require(type(repeats) is int and 1 <= repeats <= 100, "repeats must be 1..100")
    results = []
    for run, args, repetition in cases(repeats):
        with tempfile.TemporaryDirectory(prefix="trustbound-concurrent-") as directory:
            try:
                result = run(directory, *args)
            except Exception as exc:
                history = Path(directory) / "history.jsonl"
                prefix = [json.loads(line) for line in history.read_text().splitlines()] if history.exists() else []
                raise ValueError(json.dumps({"scenario": run.__name__, "arguments": args,
                                            "repetition": repetition, "error": str(exc),
                                            "executed_prefix": prefix})) from exc
        results.append({"repetition": repetition, **result})
    return {"checks_passed": True, "generated_cases": len(results), "repetitions": repeats,
            "resolved_cases": sum(r["resolved"] for r in results),
            "pending_cases": sum(r["outstanding_rights"] > 0 for r in results),
            "stale_read_conflict_cases": sum(r["observation_conflicts"] > 0 for r in results),
            "conflict_free_concurrent_reconciliation": all(not r["observation_conflicts"] for r in results),
            "max_capture_invocations_per_identity": max(r["max_capture_invocations_per_identity"] for r in results),
            "max_paid_effects_per_identity": max(r["max_paid_effects_per_identity"] for r in results),
            "python": platform.python_version(), "platform": platform.platform(),
            "scope": "Bounded threaded workers with separate SQLite connections, 2/4 payments and 2/4/8 contending clients; controlled races and three default repetitions, not exhaustive concurrency or the serial socket server.",
            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                "research/concurrent_clients/evaluate.py", "research/support.py", "src/trustbound/stripe_gate.py", "src/trustbound/credential_service.py")},
            "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    report = write_report(args.output, lambda: run_suite(args.repeats))
    print(json.dumps({k: v for k, v in report.items() if k not in {"cases", "source_sha256"}}))


if __name__ == "__main__":
    main()
