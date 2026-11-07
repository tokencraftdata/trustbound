"""Check saved sanitized provider evidence; never contacts a payment API."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    results = root / "results"
    load = lambda name: json.loads((results / name).read_text())
    initial = load("stripe_gate_2026-11-01/report.json")
    failed_recovery = load("stripe_gate_recovery_2026-11-01/report.json")
    diagnostic = load("stripe_gate_recovery_2026-11-01/diagnostic.json")
    final = load("stripe_gate_resolved_2026-11-01/report.json")
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
        assert condition, name
    calls = [*initial["calls"], *failed_recovery["calls"], *diagnostic["calls"], *final["calls"]]
    check("same_run", initial["run_id"] == failed_recovery["run_id"] == final["run_id"])
    check("20_attempts", len(calls) == 20)
    check("initial_failure_retained", len(initial["checks"]) == 14 and
          sum(c["passed"] for c in initial["checks"]) == 13 and not initial["all_checks_passed"])
    check("diagnostic_failure_retained", len(failed_recovery["checks"]) == 3 and
          sum(c["passed"] for c in failed_recovery["checks"]) == 2 and not failed_recovery["all_checks_passed"])
    check("15_continuation_checks_pass", len(final["checks"]) == 15 and
          all(c["passed"] for c in final["checks"]) and final["all_checks_passed"])
    created = [c["payment"] for c in calls if c["method"] == "POST" and c["path"] == "/v1/payment_intents"]
    check("three_unique_test_objects", len(created) == 3 and len({r["id"] for r in created}) == 3
          and all(r["livemode"] is False for r in created))
    manifest = {r["id"]: r for r in final["final_gate"]["records"]}
    check("only_two_manifest_entries", set(manifest) == {r["id"] for r in created[1:]})
    latest_reads = {c["payment"]["id"]: c["payment"] for c in calls
                    if c["method"] == "GET" and c["http_status"] == 200}
    check("all_three_freshly_read", set(latest_reads) == {r["id"] for r in created})
    check("terminal_totals", sorted(r["status"] for r in latest_reads.values()) == ["canceled", "canceled", "succeeded"]
          and sum(r["amount_received"] for r in latest_reads.values()) == 200
          and sum(r["amount_capturable"] for r in latest_reads.values()) == 0)
    check("manifest_matches_fresh_reads", all((r["status"], r["received"], r["capturable"])
          == (latest_reads[k]["status"], latest_reads[k]["amount_received"], latest_reads[k]["amount_capturable"])
          for k, r in manifest.items()))
    check("known_object_only_queries", all(c["path"].split("/")[3].split("?")[0] in latest_reads
          for c in calls if c["method"] == "GET"))
    check("no_deployment_completeness_claim", final["complete_account_mediation_verified"] is False
          and final["final_gate"]["deployment_completeness_proved"] is False)
    paths = ["formal/StripeGate.lean", "formal/check_stripe_gate.py", "src/trustbound/stripe_gate.py",
             "tests/test_stripe_gate.py", "scripts/validate_stripe_gate.py", "scripts/recover_stripe_gate_probe.py",
             "scripts/check_stripe_gate_evidence.py"]
    report = {"checks": checks, "all_checks_passed": True, "api_calls": 0,
              "http_attempts_in_saved_evidence": len(calls),
              "current_sources_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
              "source_note": "validate_stripe_gate.py now omits unsupported final_capture parameter; corrected fresh run not executed; reviewed continuation is separate",
              "scope": "consistency of saved same-processor evidence, not authenticity or exhaustive admission"}
    (results / "stripe_gate_resolved_2026-11-01/evidence-check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"offline_checks_passed": len(checks), "saved_http_attempts": len(calls)}))


if __name__ == "__main__":
    main()
