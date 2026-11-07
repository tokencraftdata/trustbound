"""Check saved real test-API evidence without making provider requests."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "results/controlled_merchant_2026-11-03"
    report = json.loads((output / "report.json").read_text())
    assert report["path_checks_passed"] and len(report["path_checks"]) == 21
    assert all(c["passed"] for c in report["path_checks"])
    assert not report["agent_non_bypass_established"] and not report["payment_completeness_established"]
    assert report["http_attempts_recorded"] == 9
    assert len(report["broker_calls"]) == 5 and len(report["observer_attempts"]) == 4
    assert all(c["http_status"] == 200 and c["request_id"] for c in report["broker_calls"] + report["observer_attempts"])
    assert all(not v["has_more"] for phase in ("baseline_provider_lists", "final_provider_lists") for v in report[phase].values())
    audit = report["same_user_access_audit"]
    assert audit["executed"] and audit["credential_readable"] and audit["journal_writable"]
    assert not audit["isolation_established"]
    reconciled = report["reconciliation"]
    assert reconciled["observed_delta_matches_manifest"] and len(reconciled["known_comparisons"]) == 1
    matched = reconciled["known_comparisons"][0]
    assert matched["gate_received"] == matched["processor_received"] == matched["charges_captured"] == 200
    with sqlite3.connect((args.private_dir / "request-journal.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        rows = [dict(zip(("n", "method", "path", "idempotency_key", "body", "state"), row)) for row in db.execute("SELECT * FROM request ORDER BY n")]
    for row in rows:
        row["body"] = json.loads(row["body"])
        assert row["state"] == "response_received"
    assert len(rows) == 5
    assert sum(r["method"] == "POST" and r["path"].endswith("/capture") for r in rows) == 1
    with sqlite3.connect((args.private_dir / "gate.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        commands = [dict(zip(("command_id", "payment_id", "action", "claimed"), row)) for row in db.execute("SELECT * FROM command ORDER BY id")]
        epoch = db.execute("SELECT id,closed FROM epoch").fetchone()
    assert epoch == (report["run_id"], 1)
    assert len(commands) == 2 and {c["action"] for c in commands} == {"confirm", "capture"}
    assert all(c["claimed"] == 1 and c["payment_id"] == report["payment_id"] for c in commands)
    (output / "durable-journal.json").write_text(json.dumps({"requests": rows, "commands": commands, "epoch": epoch}, indent=2) + "\n")
    for name, expected in (("controlled_merchant_unit_2026-11-03.xml", 9), ("controlled_merchant_full_2026-11-03.xml", 222)):
        xml = ET.parse(ROOT / "results" / name).getroot()
        assert len(list(xml.iter("testcase"))) == expected
        assert not any(list(xml.iter(tag)) for tag in ("failure", "error", "skipped"))
    sources = ["scripts/validate_controlled_merchant.py", "scripts/check_controlled_merchant_evidence.py",
        "scripts/validate_stripe_sandbox.py", "scripts/reconcile_stripe_account.py",
        "src/trustbound/credential_service.py", "src/trustbound/stripe_gate.py", "tests/test_controlled_merchant.py"]
    summary = {"path_checks_passed": 21, "real_test_api_requests": 9, "test_amount_captured_minor": 200,
        "new_unit_tests_passed": 9, "full_suite_passed": 222, "credential_isolation_established": False,
        "same_user_boundary_properties_failed": ["credential_unreadable", "journal_unwritable"],
        "complete_admission_coverage_established": False, "processor_records_reconciled": True,
        "independent_issuer_evidence": False, "formal_checks_rerun_this_followup": False,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "source_sha256"}))


if __name__ == "__main__":
    main()
