"""One 200-cent Stripe TEST path through the fixed gate, without Docker.

Not a secure deployment: same-user credential/journal access is measured and
reported, never treated as absent. Observer lists use the same processor/key,
without a manifest/metadata filter; they are not an independent issuer or cut.
No retries, production keys, account changes or automatic unknown-write recovery.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from urllib.error import HTTPError
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.credential_service import CommandService
from trustbound.stripe_gate import StripeGate
from validate_stripe_sandbox import ProbeClient
from reconcile_stripe_account import get_list

FIELDS = {
    "payment_intents": ["id", "livemode", "amount", "currency", "status", "amount_received", "amount_capturable", "latest_charge"],
    "charges": ["id", "livemode", "amount", "currency", "status", "captured", "amount_captured", "payment_intent"],
}


class FixedAdapter:
    def __init__(self, api):
        self.api = api
        self.discard_capture_reply = True

    def request(self, method, path, body, idem):
        code, row = self.api.request(method, path, body, idem)
        if path.endswith("/capture") and code == 200 and self.discard_capture_reply:
            self.discard_capture_reply = False
            raise TimeoutError("injected_application_reply_discard")
        return code, row

    def retrieve(self, identity):
        code, row = self.api.request("GET", "/v1/payment_intents/" + identity)
        if code != 200:
            raise RuntimeError("authoritative_read_failed")
        return row


def reconcile_delta(baseline, final, snapshot):
    """Compare unfiltered provider observations; unknown IDs are not discarded."""
    known = {r["id"] for r in snapshot["records"]}
    before = {kind: {r["id"]: r for r in baseline[kind]["records"]} for kind in FIELDS}
    after = {kind: {r["id"]: r for r in final[kind]["records"]} for kind in FIELDS}
    new_pi = set(after["payment_intents"]) - set(before["payment_intents"])
    new_charge = set(after["charges"]) - set(before["charges"])
    unexpected_pi = new_pi - known
    unexpected_charge = [i for i in new_charge if after["charges"][i]["payment_intent"] not in known]
    prior_changed = {kind: sorted(i for i, row in before[kind].items() if after[kind].get(i) != row) for kind in FIELDS}
    comparisons = []
    for entry in snapshot["records"]:
        row = after["payment_intents"].get(entry["id"], {})
        charges = [c for c in after["charges"].values() if c["payment_intent"] == entry["id"]]
        captured = sum(c["amount_captured"] for c in charges)
        comparisons.append({"payment_id": entry["id"], "gate_received": entry["received"],
            "processor_received": row.get("amount_received"), "charges_captured": captured,
            "charge_ids": [c["id"] for c in charges],
            "matches": row.get("status") == entry["status"] == "succeeded"
                and row.get("amount_received") == captured == entry["received"] == entry["amount"]
                and row.get("amount_capturable") == 0 and row.get("currency") == "usd"
                and len(charges) == 1 and row.get("latest_charge") == charges[0]["id"]
                and all(c["currency"] == "usd" and c["captured"] is True and c["status"] == "succeeded" for c in charges)})
    return {"known_comparisons": comparisons, "new_payment_ids": sorted(new_pi),
        "new_charge_ids": sorted(new_charge), "unexpected_new_payment_ids": sorted(unexpected_pi),
        "unexpected_new_charge_ids": sorted(unexpected_charge), "preexisting_records_changed": prior_changed,
        "observed_delta_matches_manifest": bool(known) and new_pi == known and not unexpected_charge
            and not any(prior_changed.values()) and all(r["matches"] for r in comparisons),
        "account_completeness_established": False, "atomic_snapshot": False,
        "independent_issuer": False}


def audit_same_user(credential, journal):
    # Real open probes in a separate process, with no credential bytes returned
    # and no file content modified. Not supplying a key in env is insufficient.
    code = """import os,json,sys
checks={}
for label,path,flags in [('credential_readable',sys.argv[1],os.O_RDONLY),('journal_writable',sys.argv[2],os.O_WRONLY)]:
 try:
  fd=os.open(path,flags); os.close(fd); checks[label]=True
 except OSError:
  checks[label]=False
print(json.dumps({'uid':os.geteuid(),**checks}))
"""
    result = subprocess.run([sys.executable, "-c", code, str(credential), str(journal)],
        capture_output=True, text=True, timeout=10, env={"PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    if result.returncode:
        return {"executed": False, "exit_code": result.returncode, "isolation_established": False}
    return {"executed": True, **json.loads(result.stdout), "isolation_established": False}


def run(credential_file, private, output):
    os.umask(0o077)
    private.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    report = {"started_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": "real_Stripe_test_API", "production_payments": False,
        "api_version": "2026-10-28.endive", "path_checks": [], "agent_transcript": [],
        "observer_attempts": [], "path_checks_passed": False,
        "agent_non_bypass_established": False, "payment_completeness_established": False}
    api = gate = None
    try:
        config = tomllib.loads(credential_file.read_text())
        key = config["trustbound-validation"]["test_mode_api_key"]
        run_id = "tb-controlled-" + uuid.uuid4().hex
        report["run_id"] = run_id
        report["scope_declared_before_creation"] = "One 200-cent USD card/manual-confirm/manual-capture path; broader account-list deltas checked without metadata filters. Other keys/operators/automation unaudited."
        api = ProbeClient(key, private, run_id)
        report["broker_calls"] = api.calls
        gate = StripeGate(private / "gate.db", run_id)
        report["same_user_access_audit"] = audit_same_user(credential_file, private / "gate.db")
        def check(name, condition):
            report["path_checks"].append({"name": name, "passed": bool(condition)})
            if not condition:
                raise RuntimeError("path_check_failed")
        def listing(label):
            views = {}
            for kind, fields in FIELDS.items():
                attempt = {"phase": label, "resource": kind, "outcome": "unknown"}
                report["observer_attempts"].append(attempt)
                try:
                    views[kind] = get_list(key, kind, fields)
                    attempt.update(outcome="response_received", request_id=views[kind]["request_id"], http_status=200)
                except HTTPError as exc:
                    attempt.update(outcome="http_error", http_status=exc.code)
                    raise
            return views
        baseline = report["baseline_provider_lists"] = listing("before")
        body = {"amount": 200, "currency": "usd", "capture_method": "manual", "confirmation_method": "manual",
                "confirm": "false", "allowed_payment_method_types[]": "card", "metadata[trustbound_run]": run_id}
        code, row = api.request("POST", "/v1/payment_intents", body, run_id + ":create")
        check("one_inert_test_object_created", code == 200 and row.get("status") == "requires_payment_method")
        gate.register(row)
        report["payment_id"] = row["id"]
        try:
            gate.grant("pi_UnknownFixture", "confirm")
            blocked = False
        except RuntimeError as exc:
            blocked = str(exc) == "unknown_or_terminal_payment"
        check("unknown_identity_cannot_obtain_admission", blocked)
        confirm = gate.grant(row["id"], "confirm")
        capture = gate.grant(row["id"], "capture")
        gate.fence()
        try:
            gate.grant(row["id"], "capture")
            blocked = False
        except RuntimeError as exc:
            blocked = str(exc) == "epoch_fenced"
        check("fence_blocks_new_authority", blocked)
        adapter = FixedAdapter(api)
        service = CommandService(gate, adapter)
        def rpc(request):
            response = service.handle(json.dumps(request).encode())
            report["agent_transcript"].append({"request": request, "response": response})
            return response
        forbidden = [
            {"op": "create", "confirm": True}, {"op": "grant", "payment_id": row["id"]},
            {"op": "observe", "status": "canceled"}, {"op": "fence", "closed": False},
            {"op": "dispatch", "command_id": confirm, "amount": 999},
            {"op": "dispatch", "command_id": confirm, "transport": "attacker"},
            {"op": "dispatch", "command_id": confirm, "path": "/v1/payment_intents"},
            {"op": "dispatch", "command_id": 999}, {"op": "read", "path": "provider-key"},
        ]
        before = len(api.calls)
        for index, request in enumerate(forbidden):
            check("forbidden_agent_request_" + str(index), rpc(request)["ok"] is False)
        check("forbidden_requests_produce_no_provider_calls", len(api.calls) == before)
        reply = rpc({"op": "dispatch", "command_id": confirm})
        check("admitted_confirm_executes_after_fence", reply.get("ok") and reply["result"]["http_status"] == 200)
        pending = rpc({"op": "reconcile"})
        check("authorized_not_drained", pending.get("ok") and not pending["result"]["known_manifest_resolved"] and pending["result"]["retained_minor"] == 200)
        reply = rpc({"op": "dispatch", "command_id": capture})
        check("applied_capture_reply_discarded", not reply["ok"] and api.calls[-1].get("http_status") == 200 and api.calls[-1].get("payment", {}).get("status") == "succeeded")
        gate.close()
        gate = StripeGate(private / "gate.db", run_id)
        service = CommandService(gate, adapter)
        pending = rpc({"op": "snapshot"})["result"]
        check("restart_keeps_fence_and_uncertainty", pending["closed"] and not pending["known_manifest_resolved"] and pending["retained_minor"] == 200)
        before = len(api.calls)
        check("duplicate_capture_refused_after_reopen", not rpc({"op": "dispatch", "command_id": capture})["ok"] and len(api.calls) == before)
        reply = rpc({"op": "reconcile"})
        check("fresh_retrieval_resolves_known_manifest", reply.get("ok") and reply["result"]["known_manifest_resolved"] and reply["result"]["retained_minor"] == 200)
        report["final_gate"] = gate.snapshot()
        final = report["final_provider_lists"] = listing("after")
        report["reconciliation"] = reconcile_delta(baseline, final, report["final_gate"])
        check("unfiltered_processor_delta_matches_gate", report["reconciliation"]["observed_delta_matches_manifest"])
        check("no_complete_deployment_claim", report["final_gate"]["deployment_completeness_proved"] is False)
        report["path_checks_passed"] = True
    except Exception as exc:
        report["failure_type"] = type(exc).__name__
        if isinstance(exc, HTTPError):
            report["failure_http_status"] = exc.code
    finally:
        report["http_attempts_recorded"] = len(report.get("broker_calls", [])) + len(report["observer_attempts"])
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        if gate is not None:
            gate.close()
        if api is not None:
            api.db.close()
    print(json.dumps({k: report.get(k) for k in ("path_checks_passed", "http_attempts_recorded", "failure_type", "failure_http_status", "agent_non_bypass_established", "payment_completeness_established")}))
    return 0 if report["path_checks_passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-sandbox", required=True, action="store_true")
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--private-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.credential_file, args.private_dir, args.output))
