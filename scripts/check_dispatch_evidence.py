"""Validate local crash/formal artifacts and record current source provenance."""
import hashlib
import json
from pathlib import Path
import sqlite3
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "results/dispatch_boundary_2026-11-01"
    full = ET.parse(output / "full-tests.xml").getroot()
    focused = ET.parse(output / "crash-tests.xml").getroot()
    full_cases = list(full.iter("testcase"))
    focused_cases = list(focused.iter("testcase"))
    assert len(full_cases) == 170 and len(focused_cases) == 30
    assert not any(list(tree.iter(tag)) for tree in (full, focused) for tag in ("failure", "error", "skipped"))
    crashes = [c.attrib["name"] for c in focused_cases if c.attrib["name"].startswith("test_sigkill_boundary[")]
    assert len(crashes) == 13
    audit = json.loads((output / "credential-boundary.json").read_text())
    assert audit["credential_contents_read"] is False
    assert audit["readable_by_current_worker"] is True and audit["same_owner_as_worker"] is True
    formal = json.loads((root / "results/formal_dispatch_2026-11-01/summary.json").read_text())
    assert formal["source_sha256"] == hashlib.sha256((root / "formal/Dispatch.lean").read_bytes()).hexdigest()
    assert formal["checker_sha256"] == hashlib.sha256((root / "formal/check_dispatch.py").read_bytes()).hexdigest()
    exports, mutations = len(formal["exported_theorems"]), len(formal["mutations"])
    for i in range(3):
        summary = json.loads((root / f"results/dispatch_regression_{i}_2026-11-01/summary.json").read_text())
        exports += len(summary["exported_theorems"])
        mutations += len(summary["mutations"])
        assert summary["check_exit_code"] == 0
        assert all(v["proof_rejected"] for v in summary["mutations"].values())
        if "observer_model" in summary:
            observer = summary["observer_model"]
            exports += len(observer["exported_theorems"])
            mutations += len(observer["mutations"])
            assert observer["check_exit_code"] == 0 and all(v["proof_rejected"] for v in observer["mutations"].values())
    assert exports == 34 and mutations == 19 and all(v["proof_rejected"] for v in formal["mutations"].values())
    files = ["src/trustbound/stripe_gate.py", "tests/test_dispatch_crashes.py", "tests/dispatch_crash_worker.py",
             "formal/Dispatch.lean", "formal/check_dispatch.py", "scripts/check_dispatch_evidence.py"]
    report = {"full_tests_passed": 170, "focused_tests_passed": 30,
              "sigkill_cases": crashes, "formal_exports_checked": exports,
              "rejected_mutations": mutations, "sqlite_version": sqlite3.sqlite_version,
              "provider": "separate local SQLite simulator without deduplication",
              "real_payment_api_calls_this_update": 0, "credential_isolation_verified": False,
              "current_sources_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in files},
              "limits": ["process death only; no power loss", "single-worker abstract proof",
                         "trusted storage and transport", "no source-to-model refinement or faithful export proof"]}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("full_tests_passed", "focused_tests_passed", "formal_exports_checked", "rejected_mutations")}))


if __name__ == "__main__":
    main()
