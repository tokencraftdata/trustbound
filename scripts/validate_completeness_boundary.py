"""Docker-free paired execution of the gate with a persistent local simulator.

Not a provider integration or isolation test. The independent database is an
experimental ground-truth ledger, NOT an independent organization or witness.
Ground truth never enters the gate's closure decision.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.credential_service import CommandService, intent
from trustbound.stripe_gate import StripeGate


class Processor:
    """Two-object toy lifecycle; terminal objects reject new effects."""
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE object(id TEXT PRIMARY KEY, amount INTEGER, status TEXT)")
        self.db.execute("CREATE TABLE effect(id TEXT PRIMARY KEY, amount INTEGER)")
        self.db.executemany("INSERT INTO object VALUES (?, ?, 'requires_payment_method')",
                            [("pi_Boundary1", 200), ("pi_Hidden1", 100)])
        self.db.commit()
        self.lose_capture_reply = True
        self.fail_read = False

    def retrieve(self, identity):
        if self.fail_read:
            raise TimeoutError("injected_read_timeout")
        amount, status = self.db.execute("SELECT amount,status FROM object WHERE id=?", (identity,)).fetchone()
        return {**intent(status), "id": identity, "amount": amount,
                "amount_received": amount if status == "succeeded" else 0,
                "amount_capturable": amount if status == "requires_capture" else 0}

    def request(self, method, path, body, idem):
        parts = path.split("/")
        if method != "POST" or len(parts) != 5 or parts[1:3] != ["v1", "payment_intents"]:
            raise ValueError("unsupported_request")
        identity, action = parts[3:]
        row = self.retrieve(identity)
        if action == "confirm" and body == {"payment_method": "pm_card_visa"} and row["status"] == "requires_payment_method":
            status = "requires_capture"
        elif action == "capture" and body == {} and row["status"] == "requires_capture":
            status = "succeeded"
        else:
            return 400, {"error": "unexpected_state"}
        with self.db:
            self.db.execute("UPDATE object SET status=? WHERE id=?", (status, identity))
            if action == "capture":
                self.db.execute("INSERT INTO effect VALUES (?,?)", (identity, row["amount"]))
        if action == "capture" and self.lose_capture_reply:
            self.lose_capture_reply = False
            raise TimeoutError("effect_committed_reply_discarded")
        return 200, self.retrieve(identity)

    def truth(self):
        # Evaluation only. Never supplied to the gate or service.
        return [dict(zip(("id", "amount"), row)) for row in
                self.db.execute("SELECT id,amount FROM effect ORDER BY id")]


def execute(directory, bypass):
    directory.mkdir()
    processor = Processor(directory / "processor.db")
    gate_path = directory / "gate.db"
    gate = StripeGate(gate_path, "fixed-economic-scope")
    service = CommandService(gate, processor)
    checks, transcript = [], []
    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})
    def rpc(op, **extra):
        request = {"op": op, **extra}
        reply = service.handle(json.dumps(request).encode())
        transcript.append({"request": request, "reply": reply})
        return reply
    def rejects(operation, message):
        try:
            operation()
        except RuntimeError as exc:
            return message in str(exc)
        return False
    try:
        gate.register(processor.retrieve("pi_Boundary1"))
        check("unregistered_activation_refused_by_gate", rejects(
            lambda: gate.grant("pi_Hidden1", "confirm"), "unknown_or_terminal"))
        confirm = gate.grant("pi_Boundary1", "confirm")
        capture = gate.grant("pi_Boundary1", "capture")
        gate.fence()
        check("registration_after_fence_refused", rejects(
            lambda: gate.register(processor.retrieve("pi_Hidden1")), "fenced"))
        check("grant_after_fence_refused", rejects(
            lambda: gate.grant("pi_Boundary1", "capture"), "fenced"))
        check("earlier_confirm_can_execute_after_fence", rpc("dispatch", command_id=confirm)["ok"])
        check("caller_supplied_terminal_receipt_refused", not rpc("observe", status="canceled")["ok"])
        pending = rpc("reconcile")["result"]
        check("fence_with_pending_capture_is_not_drain", not pending["known_manifest_resolved"] and pending["retained_minor"] == 200)
        check("lost_capture_reply_remains_unresolved", not rpc("dispatch", command_id=capture)["ok"])
        check("capture_effect_committed_before_reply_loss", processor.truth() == [{"id": "pi_Boundary1", "amount": 200}])
        processor.fail_read = True
        check("failed_read_does_not_certify_terminal", not rpc("reconcile")["ok"])
        uncertain = rpc("snapshot")["result"]
        check("uncertain_exposure_retained", not uncertain["known_manifest_resolved"] and uncertain["retained_minor"] == 200)
        processor.fail_read = False
        gate.close()
        gate = StripeGate(gate_path, "fixed-economic-scope")
        service = CommandService(gate, processor)
        check("fence_survives_reopen", rpc("snapshot")["result"]["closed"])
        check("restart_duplicate_dispatch_refused", not rpc("dispatch", command_id=capture)["ok"])
        resolved = rpc("reconcile")["result"]
        check("fresh_known_object_read_resolves_manifest", resolved["known_manifest_resolved"] and resolved["retained_minor"] == 200)
        check("deployment_completeness_not_claimed", resolved["deployment_completeness_proved"] is False)
        before = processor.truth()
        if bypass:
            # Explicit premise violation: another credential holder activates an
            # unknown object in the SAME predeclared scope after local closure.
            for action, body in (("confirm", {"payment_method": "pm_card_visa"}), ("capture", {})):
                code, _ = processor.request("POST", "/v1/payment_intents/pi_Hidden1/" + action, body, "outside-gate")
                check("bypass_" + action + "_executed", code == 200)
        final = rpc("reconcile")["result"]
        check("known_manifest_stays_resolved", final == resolved)
        after = processor.truth()
        # Positive terminality control in the toy provider, not a Stripe test.
        code, _ = processor.request("POST", "/v1/payment_intents/pi_Boundary1/capture", {}, "late-delivery")
        check("known_terminal_object_rejects_late_capture", code == 400 and processor.truth() == after)
        return {"checks": checks, "public_transcript": transcript,
                "public_final_snapshot": gate.snapshot(),
                "grader_only_before": before, "grader_only_after": after}
    finally:
        gate.close()
        processor.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Never reuse databases or overwrite a prior run.
    args.output.mkdir(parents=True, exist_ok=False)
    honest = execute(args.output / "mediated", False)
    bypass = execute(args.output / "bypass", True)
    comparisons = {
        "identical_public_transcripts": honest["public_transcript"] == bypass["public_transcript"],
        "identical_final_gate_snapshots": honest["public_final_snapshot"] == bypass["public_final_snapshot"],
        "mediated_total_200": sum(x["amount"] for x in honest["grader_only_after"]) == 200,
        "bypass_total_300": sum(x["amount"] for x in bypass["grader_only_after"]) == 300,
        "bypass_effect_after_known_manifest_resolution": bypass["grader_only_before"] != bypass["grader_only_after"],
        "complete_provider_ledger_distinguishes_worlds": honest["grader_only_after"] != bypass["grader_only_after"],
    }
    passed = all(c["passed"] for world in (honest, bypass) for c in world["checks"]) and all(comparisons.values())
    sources = [Path(__file__).resolve(), ROOT / "src/trustbound/stripe_gate.py", ROOT / "src/trustbound/credential_service.py"]
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "all_checks_passed": passed,
              "assertions": sum(len(w["checks"]) for w in (honest, bypass)) + len(comparisons),
              "comparisons": comparisons, "mediated": honest, "bypass": bypass,
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
              "provider": "local_toy_simulator", "real_provider_calls": 0,
              "os_isolation_tested": False, "deployment_completeness_established": False,
              "interpretation": "Known-ID RPC observations cannot distinguish this alternate-route effect. Full simulated provider-ledger access can; no claim of Stripe API indistinguishability or independent witness validation."}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("all_checks_passed", "assertions", "comparisons", "real_provider_calls", "os_isolation_tested")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
