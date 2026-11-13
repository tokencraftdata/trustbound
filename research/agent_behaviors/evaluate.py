"""Evaluate five scripted request-only clients against the actual command service.

Forty deterministic cases, not LLM evaluations or concurrent executions. Policies
receive only a request/reply callback. This is a harness boundary, not OS isolation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from research.support import PAYMENT, SinglePaymentProvider, require, write_report
from trustbound.credential_service import CommandService
from trustbound.stripe_gate import StripeGate

POLICIES = ("single_attempt", "bounded_retry", "snapshot_polling",
            "reconcile_after_attempt", "invalid_and_replayed_requests")
FAULTS = ("normal", "lost_reply", "pending_provider", "terminal_cancel")
PRIVATE_MARKER = "TB_AGENT_EVAL_SYNTHETIC_PRIVATE"


def encode(request):
    return json.dumps(request, sort_keys=True, separators=(",", ":")).encode()


DISPATCH = encode({"op": "dispatch", "command_id": 2})
SNAPSHOT = encode({"op": "snapshot"})
RECONCILE = encode({"op": "reconcile"})
INVALID = (
    encode({"op": "grant", "payment_id": PAYMENT}),
    encode({"op": "dispatch", "command_id": 2, "amount": 1}),
    encode({"op": "observe", "status": "canceled"}),
    encode({"op": "dispatch", "command_id": 9999}),
    encode({"op": "fence", "closed": False}),
)


def run_policy(name, exchange):
    """Policies see only service responses; no gate, provider, or oracle objects."""
    require(name in POLICIES, "unknown policy")
    if name == "invalid_and_replayed_requests":
        for raw in INVALID:
            exchange(raw)
    reply = exchange(DISPATCH)
    if name == "bounded_retry":
        for _ in range(2):
            if reply.get("ok") and reply.get("result", {}).get("http_status") == 200:
                break
            reply = exchange(DISPATCH)
    elif name == "invalid_and_replayed_requests":
        exchange(DISPATCH)
        exchange(DISPATCH)
    if name in {"reconcile_after_attempt", "invalid_and_replayed_requests"}:
        exchange(RECONCILE)
    for _ in range(3 if name == "snapshot_polling" else 1):
        exchange(SNAPSHOT)


class BehaviorProvider(SinglePaymentProvider):
    """Single-payment simulator with retrieval and indefinitely pending requests.

    Pending mode records a transport invocation but leaves the source nonterminal.
    It represents unresolved provider work, not a claim abandoned before send.
    """
    def __init__(self, path, fault):
        super().__init__(path)
        self.fault = fault

    def request(self, method, path, body, idem):
        if path.endswith("/capture") and self.fault == "pending_provider":
            require((method, path, body, idem) == (
                "POST", f"/v1/payment_intents/{PAYMENT}/capture", {},
                "schedule-epoch:dispatch:2"), "wrong pending dispatch target")
            with self.db:
                self.db.execute("INSERT INTO calls(action) VALUES ('capture')")
            raise TimeoutError("provider work remains pending")
        self.lose_reply = self.fault == "lost_reply"
        code, observation = super().request(method, path, body, idem)
        return code, {**observation, "private_marker": PRIVATE_MARKER}

    def retrieve(self, payment_id):
        require(payment_id == PAYMENT, "wrong retrieval identity")
        return {**self.observation(), "private_marker": PRIVATE_MARKER}


@dataclass
class Expected:
    """Input-driven expectations, never inferred from implementation snapshots."""
    fault: str
    claimed: bool = False
    observed: str = "uncertain"
    capturable: int = 0

    @property
    def source(self):
        if self.fault == "terminal_cancel":
            return "canceled"
        if self.claimed and self.fault in {"normal", "lost_reply"}:
            return "succeeded"
        return "requires_capture"

    def public(self):
        return {"closed": True, "known_manifest_resolved": self.observed != "uncertain",
                "retained_minor": 0 if self.observed == "canceled" else 200,
                "has_contract_conflicts": False, "deployment_completeness_proved": False}

    def reply(self, raw):
        if raw == RECONCILE:
            self.observed = self.source if self.source != "requires_capture" else "uncertain"
            self.capturable = 200 if self.source == "requires_capture" else 0
        if raw in {SNAPSHOT, RECONCILE}:
            return {"ok": True, "result": self.public()}
        if raw == DISPATCH and not self.claimed:
            self.claimed = True
            if self.fault in {"normal", "terminal_cancel"}:
                return {"ok": True, "result": {
                    "payment_id": PAYMENT, "action": "capture",
                    "http_status": 400 if self.fault == "terminal_cancel" else 200,
                    "requires_authoritative_reconciliation": True}}
        return {"ok": False, "error": "request_rejected_or_unresolved"}

    def check(self, gate, provider):
        snapshot = gate.snapshot()
        require({key: snapshot[key] for key in self.public()} == self.public(),
                "closure or public state differs from expected contract")
        require(snapshot["records"] == [{"id": PAYMENT, "amount": 200,
                "status": self.observed, "received": 200 if self.observed == "succeeded" else 0,
                "capturable": self.capturable}], "journal or observation differs")
        require(snapshot["commands"] == [
            {"id": 1, "payment_id": PAYMENT, "action": "confirm", "claimed": 1},
            {"id": 2, "payment_id": PAYMENT, "action": "capture", "claimed": int(self.claimed)}],
            "command authority or claim differs")
        require(snapshot["contract_conflicts"] == [], "unexpected contract conflict")
        require(provider.status == self.source, "provider terminality differs")
        calls = provider.db.execute("SELECT action FROM calls ORDER BY rowid").fetchall()
        require(calls == [("confirm",)] + [("capture",)] * int(self.claimed),
                "extra or missing capture invocation")
        effects = [row[0] for row in provider.db.execute("SELECT identity FROM effects")]
        require(effects == ([PAYMENT] if self.source == "succeeded" else []),
                "extra or missing payment effect")
        require(not snapshot["known_manifest_resolved"] or self.source != "requires_capture",
                "false closure with effective source authority")
        return snapshot, {"status": provider.status, "calls": [row[0] for row in calls],
                          "effects": effects, "outstanding_rights": int(self.source == "requires_capture")}


def run_case(directory, policy, fault, restart, gate_type=StripeGate, service_type=CommandService):
    require(policy in POLICIES and fault in FAULTS, "unknown case")
    directory = Path(directory)
    gate = gate_type(directory / "gate.db", "schedule-epoch")
    provider = BehaviorProvider(directory / "provider.db", fault)
    expected = Expected(fault)
    history = []
    actor = "agent"
    try:
        # Trusted setup approves commands; no policy can create or grant one.
        gate.register(provider.observation())
        require(gate.grant(PAYMENT, "confirm") == 1, "unexpected confirmation ID")
        gate.dispatch(1, provider)
        require(gate.grant(PAYMENT, "capture") == 2, "unexpected capture ID")
        gate.fence()
        if fault == "terminal_cancel":
            provider.cancel()
        expected.check(gate, provider)

        def exchange(raw):
            nonlocal gate, provider
            predicted = expected.reply(raw)
            actual = service_type(gate, provider).handle(raw)
            event = {"actor": actor, "request": json.loads(raw), "response": actual}
            history.append(event)
            require(actual == predicted, "service reply differs from expected contract")
            require(PRIVATE_MARKER not in json.dumps(actual), "private provider data exposed")
            event["gate"], event["provider"] = expected.check(gate, provider)
            if restart:
                gate.close()
                provider.db.close()
                gate = gate_type(directory / "gate.db", "schedule-epoch")
                provider = BehaviorProvider(directory / "provider.db", fault)
                reopened = expected.check(gate, provider)
                require(reopened == (event["gate"], event["provider"]), "reopen changed state")
            return actual

        run_policy(policy, exchange)
        before = gate.snapshot()["known_manifest_resolved"]
        agent_requests = len(history)
        # This is a separate operator action, not credited to the agent policy.
        actor = "operator"
        exchange(RECONCILE)
        final, source = expected.check(gate, provider)
        return {"policy": policy, "fault": fault, "restart_after_each_request": restart,
                "agent_requests": agent_requests,
                "agent_dispatch_requests": sum(e["actor"] == "agent" and e["request"] == {"op": "dispatch", "command_id": 2} for e in history),
                "agent_reconciliation_requests": sum(e["actor"] == "agent" and e["request"] == {"op": "reconcile"} for e in history),
                "resolved_after_agent": before,
                "resolved_after_operator": final["known_manifest_resolved"],
                "capture_invocations": source["calls"].count("capture"),
                "paid_effects": len(source["effects"]),
                "outstanding_rights": source["outstanding_rights"],
                "history": history}
    except Exception as exc:
        raise ValueError(json.dumps({"policy": policy, "fault": fault, "restart": restart,
                                    "executed_prefix": history, "error": str(exc)})) from exc
    finally:
        gate.close()
        provider.db.close()


def run_suite():
    results = []
    for policy in POLICIES:
        for fault in FAULTS:
            for restart in (False, True):
                with tempfile.TemporaryDirectory(prefix="trustbound-agent-") as directory:
                    results.append(run_case(directory, policy, fault, restart))
    rows = []
    for policy in POLICIES:
        group = [r for r in results if r["policy"] == policy]
        rows.append({"policy": policy, "cases": len(group),
                     **{key: sum(r[key] for r in group) for key in (
                         "agent_requests", "agent_dispatch_requests", "agent_reconciliation_requests",
                         "resolved_after_agent", "resolved_after_operator", "capture_invocations", "paid_effects")}})
    return {"checks_passed": True, "generated_cases": len(results),
            "policies": list(POLICIES), "faults": list(FAULTS),
            "resolved_after_agent": sum(r["resolved_after_agent"] for r in results),
            "resolved_after_operator": sum(r["resolved_after_operator"] for r in results),
            "pending_after_operator": sum(not r["resolved_after_operator"] for r in results),
            "max_capture_invocations_per_case": max(r["capture_invocations"] for r in results),
            "max_paid_effects_per_case": max(r["paid_effects"] for r in results),
            "python": platform.python_version(), "platform": platform.platform(),
            "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
                "research/agent_behaviors/evaluate.py", "research/support.py",
                "src/trustbound/stripe_gate.py", "src/trustbound/credential_service.py")},
            "scope": "Five scripted request-only policies; four provider modes; with/without close-reopen after each request. One payment, serial execution, no LLMs, real-provider calls, host-isolation proof or new Lean certificates.",
            "per_policy": rows, "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = write_report(args.output, run_suite)
    print(json.dumps({key: report[key] for key in (
        "checks_passed", "generated_cases", "resolved_after_agent", "resolved_after_operator",
        "pending_after_operator", "max_capture_invocations_per_case", "max_paid_effects_per_case", "per_policy")}))


if __name__ == "__main__":
    main()
