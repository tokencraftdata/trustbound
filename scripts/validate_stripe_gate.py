"""One bounded real Stripe test-API experiment for the constrained gate.

Creates three synthetic PaymentIntents (100+100+200 USD cents); captures at most
200 test cents. No booking, live credential, account listing or automatic retry.
The grader deliberately sends late requests to test provider rejection. These
are known-object negative probes, not a claim all account access is mediated.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from validate_stripe_sandbox import ProbeClient
from trustbound.stripe_gate import StripeGate


def run(key, private, output):
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    run_id = "tb-gate-" + uuid.uuid4().hex
    api = ProbeClient(key, private, run_id)
    gate = StripeGate(private / "gate.db", run_id)
    report = {"run_id": run_id, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "environment": "real_stripe_test_API", "api_version": "2026-10-28.endive",
              "checks": [], "calls": api.calls, "all_checks_passed": False,
              "complete_account_mediation_verified": False,
              "provider_epoch_fence_obtained": False,
              "independent_issuer_evidence": False, "production_payment": False}

    def check(name, condition):
        report["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise RuntimeError("check_failed:" + name)

    def create(amount, label):
        # No customer, payment method, confirmation token, hooks or automation.
        body = {"amount": amount, "currency": "usd", "capture_method": "manual",
                "confirmation_method": "manual", "confirm": "false",
                "allowed_payment_method_types[]": "card",
                "metadata[trustbound_run]": run_id, "metadata[scenario]": label}
        code, row = api.request("POST", "/v1/payment_intents", body, run_id + ":create-" + label)
        check(label + "_created_inert", code == 200 and row.get("status") == "requires_payment_method"
              and row.get("confirmation_method") == "manual" and row.get("capture_method") == "manual"
              and row.get("payment_method") is None and row.get("customer") is None
              and row.get("payment_method_types") == ["card"] and row.get("amount_received") == 0
              and row.get("amount_capturable") == 0)
        return row

    def action(row, verb, label, body=None):
        return api.request("POST", "/v1/payment_intents/" + row["id"] + "/" + verb,
                           body or {}, run_id + ":" + label)

    def retrieve(row):
        code, fresh = api.request("GET", "/v1/payment_intents/" + row["id"])
        check("fresh_read_" + str(len(api.calls)), code == 200 and fresh.get("id") == row["id"])
        return fresh

    try:
        orphan = create(100, "discarded-create")
        # Grader retains response for cleanup; the gate never sees it. This is
        # application-boundary loss, not a real transport timeout.
        try:
            gate.grant(orphan["id"], "confirm")
            blocked = False
        except RuntimeError:
            blocked = True
        check("unregistered_object_cannot_obtain_dispatch", blocked)
        cancel_target = create(100, "cancel-before-late-confirm")
        gate.register(cancel_target)
        late_confirm = gate.grant(cancel_target["id"], "confirm")
        paid_target = create(200, "pregranted-capture")
        gate.register(paid_target)
        confirm = gate.grant(paid_target["id"], "confirm")
        check("durable_confirm_identity", gate.claim(confirm) == (paid_target["id"], "confirm"))
        code, authorized = action(paid_target, "confirm", "authorize", {"payment_method": "pm_card_visa"})
        check("registered_object_authorized", code == 200 and authorized.get("status") == "requires_capture"
              and authorized.get("amount_capturable") == 200)
        late_capture = gate.grant(paid_target["id"], "capture")
        gate.fence()
        gate.close()
        gate = StripeGate(private / "gate.db", run_id)
        try:
            gate.grant(cancel_target["id"], "capture")
            blocked = False
        except RuntimeError as exc:
            blocked = str(exc) == "epoch_fenced"
        check("restart_fence_blocks_new_dispatch", blocked)
        report["at_fence"] = gate.snapshot()
        check("fence_alone_retains_unknown_exposure", report["at_fence"]["retained_minor"] == 300
              and not report["at_fence"]["known_manifest_resolved"])

        code, canceled = action(cancel_target, "cancel", "cancel-before-delivery")
        check("provider_cancel_succeeded", code == 200 and canceled.get("status") == "canceled")
        gate.observe(retrieve(cancel_target))
        check("prior_confirm_claimable_after_fence", gate.claim(late_confirm) == (cancel_target["id"], "confirm"))
        code, rejected = action(cancel_target, "confirm", "late-confirm", {"payment_method": "pm_card_visa"})
        check("late_confirm_rejected_after_cancel", code == 400 and
              rejected.get("error", {}).get("code") == "payment_intent_unexpected_state")

        check("prior_capture_claimable_after_fence", gate.claim(late_capture) == (paid_target["id"], "capture"))
        # Default final_capture=true is documented; the explicit parameter was
        # rejected in the retained initial test on this account/API version.
        code, paid = action(paid_target, "capture", "post-fence-capture")
        check("earlier_right_executes_after_fence", code == 200 and paid.get("status") == "succeeded"
              and paid.get("amount_received") == 200 and paid.get("amount_capturable") == 0)
        gate.observe(retrieve(paid_target))
        code, rejected = action(paid_target, "capture", "late-capture-negative-probe")
        check("capture_after_success_rejected", code == 400 and
              rejected.get("error", {}).get("code") == "payment_intent_unexpected_state")
        gate.observe(retrieve(paid_target))
        untouched = retrieve(orphan)
        check("omitted_inert_object_still_has_no_effect", untouched.get("status") == "requires_payment_method"
              and untouched.get("amount_received") == 0 and untouched.get("amount_capturable") == 0)
        code, cleanup = action(orphan, "cancel", "orphan-cleanup")
        check("unused_orphan_canceled", code == 200 and cleanup.get("status") == "canceled")
        final_orphan = retrieve(orphan)
        check("orphan_cleanup_verified", final_orphan.get("status") == "canceled"
              and final_orphan.get("amount_received") == 0)
        report["final_gate"] = gate.snapshot()
        check("two_known_objects_resolved", report["final_gate"]["known_manifest_resolved"]
              and len(report["final_gate"]["records"]) == 2
              and report["final_gate"]["retained_minor"] == 200)
        check("orphan_not_retroactively_added_to_manifest", orphan["id"] not in
              {r["id"] for r in report["final_gate"]["records"]})
        report["all_checks_passed"] = True
    except Exception as exc:
        # Deliberately avoid arbitrary exception text that could contain secrets.
        report["failure_type"] = type(exc).__name__
    finally:
        report["http_attempts_recorded"] = len(api.calls)
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        gate.close()
        api.db.close()
    print(json.dumps({"all_checks_passed": report["all_checks_passed"],
                      "checks": len(report["checks"]), "http_attempts": len(api.calls),
                      "failure_type": report.get("failure_type")}))
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-sandbox", action="store_true", required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    raise SystemExit(run(os.environ["TRUSTBOUND_STRIPE_TEST_KEY"], args.private_dir, args.output))
