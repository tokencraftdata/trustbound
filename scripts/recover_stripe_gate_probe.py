"""Explicit reviewed recovery of the retained final_capture HTTP-400 probe.

Not an automatic retry path. Uses only IDs from that probe; fresh retrieval must
establish the expected known-object state before a single default final capture.
"""
import json
from pathlib import Path
import re
from validate_stripe_sandbox import ProbeClient
from trustbound.stripe_gate import StripeGate


def recover(key, private, initial_report, output, diagnostic=None):
    old = json.loads(initial_report.read_text())
    assert not old["all_checks_passed"]
    assert old["checks"][-1] == {"name": "earlier_right_executes_after_fence", "passed": False}
    assert old["calls"][-1]["http_status"] == 400
    created = [c["payment"] for c in old["calls"] if c["method"] == "POST"
               and c["path"] == "/v1/payment_intents" and c["http_status"] == 200]
    assert len(created) == 3
    orphan, canceled, target = created
    assert [r["amount"] for r in created] == [100, 100, 200]
    sub = private / output.name
    sub.mkdir(mode=0o700, exist_ok=False)
    output.mkdir(exist_ok=False)
    api = ProbeClient(key, sub, old["run_id"])
    gate = StripeGate(private / "gate.db", old["run_id"])
    report = {"run_id": old["run_id"], "calls": api.calls, "checks": [],
              "all_checks_passed": False, "explicit_reviewed_recovery": True,
              "new_objects_created": 0, "complete_account_mediation_verified": False}
    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise RuntimeError("check_failed")
    def get(row):
        code, data = api.request("GET", "/v1/payment_intents/" + row["id"])
        check("fresh_read_" + str(len(api.calls)), code == 200 and data.get("id") == row["id"])
        return data
    def post(row, verb, label, body=None):
        return api.request("POST", "/v1/payment_intents/" + row["id"] + "/" + verb,
                           body or {}, old["run_id"] + ":" + label)
    try:
        fresh = get(target)
        gate.observe(fresh)
        check("fresh_known_target_still_authorized", fresh.get("status") == "requires_capture"
              and fresh.get("amount_capturable") == 200 and fresh.get("amount_received") == 0
              and gate.snapshot()["closed"])
        # Exact replay of the rejected body/key diagnoses the error. It is not
        # a new-object creation, and the prior response was an explicit 400.
        if diagnostic is None:
            code, invalid = post(target, "capture", "post-fence-capture", {"final_capture": "true"})
            error = invalid.get("error", {})
            message = error.get("message", "")
        else:
            saved = json.loads(diagnostic.read_text())
            assert saved["calls"][0]["path"] == old["calls"][-1]["path"]
            code, message = saved["http_status"], saved["message"]
            report["diagnostic_source"] = diagnostic.name
        check("explicit_final_capture_parameter_rejected", code == 400 and
              "doesn't support multi-capture" in message and "final_capture" in message)
        code, paid = post(target, "capture", "reviewed-default-final-capture")
        check("pre_fence_right_captured_after_fence", code == 200 and paid.get("status") == "succeeded"
              and paid.get("amount_received") == 200 and paid.get("amount_capturable") == 0)
        gate.observe(get(target))
        code, rejected = post(target, "capture", "reviewed-late-capture-negative")
        check("late_capture_rejected", code == 400 and rejected.get("error", {}).get("code") == "payment_intent_unexpected_state")
        gate.observe(get(target))
        fresh_orphan = get(orphan)
        check("unregistered_object_remained_inert", fresh_orphan.get("status") == "requires_payment_method"
              and fresh_orphan.get("amount_received") == 0 and fresh_orphan.get("amount_capturable") == 0)
        code, cleanup = post(orphan, "cancel", "reviewed-orphan-cleanup")
        check("orphan_canceled", code == 200 and cleanup.get("status") == "canceled")
        final_orphan = get(orphan)
        check("orphan_cleanup_verified", final_orphan.get("status") == "canceled" and final_orphan.get("amount_received") == 0)
        gate.observe(get(canceled))
        report["final_gate"] = gate.snapshot()
        check("known_manifest_resolved", report["final_gate"]["known_manifest_resolved"]
              and report["final_gate"]["retained_minor"] == 200
              and len(report["final_gate"]["records"]) == 2)
        check("orphan_not_added_to_manifest", orphan["id"] not in {r["id"] for r in report["final_gate"]["records"]})
        report["all_checks_passed"] = True
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
    finally:
        report["http_attempts_recorded"] = len(api.calls)
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        gate.close()
        api.db.close()
    print(json.dumps({"all_checks_passed": report["all_checks_passed"],
                      "checks": len(report["checks"]), "http_attempts": len(api.calls)}))
    return 0 if report["all_checks_passed"] else 1
