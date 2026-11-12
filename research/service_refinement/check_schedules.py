"""Bounded operation-order checks against an independent, one-payment oracle.

These execute SQLite-backed service/provider states. They are finite Python
checks, not additional Lean proofs or an exhaustive concurrency exploration.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.stripe_gate import StripeGate

PAYMENT = "pi_Schedule1"
FAULTS = ("normal", "lost_reply", "abandoned_claim")


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Provider:
    """Separate durable simulator: cancellation and success are irreversible."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS state(status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calls(action TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS effects(identity TEXT NOT NULL);
        """)
        if not self.db.execute("SELECT 1 FROM state").fetchone():
            with self.db:
                self.db.execute("INSERT INTO state VALUES ('requires_payment_method')")
        self.lose_reply = False

    @property
    def status(self):
        return self.db.execute("SELECT status FROM state").fetchone()[0]

    def observation(self):
        return {
            "id": PAYMENT, "object": "payment_intent", "livemode": False,
            "amount": 200, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": self.status,
            "amount_received": 200 if self.status == "succeeded" else 0,
            "amount_capturable": 200 if self.status == "requires_capture" else 0,
        }

    def request(self, method, path, body, idem):
        action = path.rsplit("/", 1)[-1]
        require(method == "POST" and path == f"/v1/payment_intents/{PAYMENT}/{action}", "wrong dispatch target")
        require(action in {"confirm", "capture"}, "unsupported dispatch")
        require(body == ({"payment_method": "pm_card_visa"} if action == "confirm" else {}), "wrong dispatch body")
        require(idem == f"schedule-epoch:dispatch:{1 if action == 'confirm' else 2}", "wrong command identity")
        paid = False
        with self.db:
            self.db.execute("INSERT INTO calls VALUES (?)", (action,))
            if action == "confirm" and self.status == "requires_payment_method":
                self.db.execute("UPDATE state SET status='requires_capture'")
            elif action == "capture" and self.status == "requires_capture":
                self.db.execute("UPDATE state SET status='succeeded'")
                self.db.execute("INSERT INTO effects VALUES (?)", (PAYMENT,))
                paid = True
            else:
                return 400, {}
        if paid and self.lose_reply:
            raise TimeoutError("injected lost reply after provider commit")
        return 200, self.observation()

    def cancel(self):
        with self.db:
            if self.status == "requires_capture":
                self.db.execute("UPDATE state SET status='canceled'")


@dataclass
class Oracle:
    """Expected contract state, advanced only from test inputs, not gate rows."""

    fenced: bool = False
    granted: bool = False
    claimed: bool = False
    provider: str = "requires_capture"
    observed: str = "uncertain"
    capturable: int = 0
    calls: int = 0

    def advance(self, action, fault):
        outcome = "ok"
        if action == "grant":
            if self.fenced or self.granted or self.observed != "uncertain":
                return "rejected"
            self.granted = True
        elif action == "fence":
            self.fenced = True
        elif action == "dispatch":
            if not self.granted or self.claimed:
                return "rejected"
            self.claimed = True
            if fault != "abandoned_claim":
                self.calls += 1
                if self.provider == "requires_capture":
                    self.provider = "succeeded"
                    if fault == "lost_reply":
                        outcome = "lost_reply"
        elif action == "cancel":
            if self.provider == "requires_capture":
                self.provider = "canceled"
        elif action == "observe":
            self.observed = self.provider if self.provider in {"succeeded", "canceled"} else "uncertain"
            self.capturable = 200 if self.provider == "requires_capture" else 0
        elif action == "register_after_fence":
            require(self.fenced, "invalid test: late registration before fence")
            return "rejected"
        else:
            raise ValueError(f"unknown test action: {action}")
        return outcome

    def check(self, gate, provider):
        snapshot = gate.snapshot()
        require(snapshot["closed"] == self.fenced, "fence persistence differs from oracle")
        require(snapshot["records"] == [{
            "id": PAYMENT, "amount": 200, "status": self.observed,
            "received": 200 if self.observed == "succeeded" else 0,
            "capturable": self.capturable,
        }], "journal or observations differ from oracle")
        commands = [{"id": 1, "payment_id": PAYMENT, "action": "confirm", "claimed": 1}]
        if self.granted:
            commands.append({"id": 2, "payment_id": PAYMENT, "action": "capture", "claimed": int(self.claimed)})
        require(snapshot["commands"] == commands, "authority/claim persistence differs from oracle")
        require(not snapshot["has_contract_conflicts"], "truthful simulated history acquired a conflict")
        require(snapshot["known_manifest_resolved"] == (self.fenced and self.observed != "uncertain"), "premature or missing closure")
        require(snapshot["retained_minor"] == (0 if self.observed == "canceled" else 200), "unsafe reservation release")
        require(provider.status == self.provider, "provider state differs from oracle")
        calls = provider.db.execute("SELECT action FROM calls").fetchall()
        require(calls == [("confirm",)] + [("capture",)] * self.calls, "extra or missing provider invocation")
        effects = [row[0] for row in provider.db.execute("SELECT identity FROM effects")]
        require(effects == ([PAYMENT] if self.provider == "succeeded" else []), "extra or missing paid effect")
        require(set(effects) <= {row["id"] for row in snapshot["records"]}, "effect omitted from journal")
        # A confirm right was issued during setup and remains outstanding until
        # the provider reaches a terminal state, even if capture was never sent.
        if self.provider == "requires_capture":
            require(not snapshot["known_manifest_resolved"], "outstanding authority lost")


def cases():
    for cancel in (False, True):
        actions = ("grant", "fence", "dispatch", "observe") + (("cancel",) if cancel else ())
        for order in itertools.permutations(actions):
            for fault in FAULTS:
                for restart in (False, True):
                    yield order, fault, restart


def run_case(directory, order, fault, restart, gate_type=StripeGate):
    """Replayable case; close/reopen both databases after each action if selected."""
    require(fault in FAULTS, "unknown fault")
    gate_path, provider_path = directory / "gate.db", directory / "provider.db"
    gate = gate_type(gate_path, "schedule-epoch")
    provider = Provider(provider_path)
    oracle = Oracle()
    history = []
    try:
        gate.register(provider.observation())
        require(gate.grant(PAYMENT, "confirm") == 1, "unexpected setup command identity")
        gate.dispatch(1, provider)
        oracle.check(gate, provider)
        # Repeated dispatches test retries even when the scheduled dispatch was
        # too early. Final reconciliation reveals effects hidden by a lost reply.
        for action in (*order, "fence", "grant", "register_after_fence", "dispatch", "dispatch", "observe"):
            expected = oracle.advance(action, fault)
            actual = "ok"
            try:
                if action == "grant":
                    require(gate.grant(PAYMENT, "capture") == 2, "unexpected capture identity")
                elif action == "dispatch":
                    if fault == "abandoned_claim":
                        gate.claim(2)
                    else:
                        provider.lose_reply = fault == "lost_reply"
                        gate.dispatch(2, provider)
                elif action == "fence":
                    gate.fence()
                elif action == "cancel":
                    provider.cancel()
                elif action == "observe":
                    gate.observe(provider.observation())
                elif action == "register_after_fence":
                    row = provider.observation()
                    row.update(id="pi_Late1", status="requires_payment_method", amount_received=0, amount_capturable=0)
                    gate.register(row)
            except TimeoutError:
                actual = "lost_reply"
            except (RuntimeError, sqlite3.IntegrityError):
                actual = "rejected"
            history.append({"action": action, "expected": expected, "actual": actual})
            require(actual == expected, f"{action}: expected {expected}, got {actual}")
            oracle.check(gate, provider)
            if restart:
                gate.close()
                provider.db.close()
                gate = gate_type(gate_path, "schedule-epoch")
                provider = Provider(provider_path)
                oracle.check(gate, provider)
        return {"order": order, "fault": fault, "restart_after_each_action": restart,
                "paid_effects": int(oracle.provider == "succeeded"),
                "outstanding_rights": int(oracle.provider == "requires_capture"),
                "resolved": gate.snapshot()["known_manifest_resolved"], "steps": len(history)}
    except Exception as exc:
        raise ValueError(json.dumps({"order": order, "fault": fault, "restart": restart,
                                    "history": history, "error": str(exc)})) from exc
    finally:
        gate.close()
        provider.db.close()


def run_suite():
    results = []
    for order, fault, restart in cases():
        with tempfile.TemporaryDirectory(prefix="trustbound-schedule-") as directory:
            results.append(run_case(Path(directory), order, fault, restart))
    require(len(results) == 864, "incomplete generated schedule set")
    return {"checks_passed": True, "generated_cases": len(results),
            "resolved_cases": sum(case["resolved"] for case in results),
            "unresolved_cases": sum(not case["resolved"] for case in results),
            "scope": "All 4! or 5! permutations of one-payment actions, three dispatch modes, with/without restart after every action. Finite Python checks, not Lean certificates or all concurrent executions.",
            "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Reserve the output first, so an existing result is never overwritten.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        try:
            report = run_suite()
        except Exception as exc:
            json.dump({"checks_passed": False, "error": str(exc)}, output, indent=2)
            raise
        json.dump(report, output, indent=2)
        output.write("\n")
    print(json.dumps({key: report[key] for key in ("checks_passed", "generated_cases", "resolved_cases", "unresolved_cases")}))


if __name__ == "__main__":
    main()
