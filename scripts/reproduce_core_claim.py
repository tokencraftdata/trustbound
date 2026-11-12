"""Reproduce the selected paper core locally, without provider credentials.

Copies only the selected source files to a new output directory, invokes the
existing checkers, and retains command logs and JUnit output. Reuses the caller's
Python environment and an explicitly selected Lean 4.19.0 installation: this is
source-isolated reproduction, not a fresh-machine/dependency installation test.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


FILES = (
    "formal/Admission.lean", "formal/StripeGate.lean",
    "formal/check_admission.py", "formal/check_stripe_gate.py",
    "formal/lean-toolchain", "src/trustbound/__init__.py",
    "src/trustbound/closure_experiment.py", "tests/test_closure_experiment.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if not __debug__:
        raise SystemExit("Assertions must be enabled; do not use python -O or PYTHONOPTIMIZE.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)  # Never overwrite a previous attempt.
    snapshot = out / "snapshot"
    for name in FILES:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    hashes = {name: digest(snapshot / name) for name in FILES}
    tmp = out / "tmp"
    tmp.mkdir()
    env = {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "TMPDIR": str(tmp), "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONPATH": str(snapshot / "src"),
    }
    python, lean = sys.executable, str(args.lean.resolve())
    started = datetime.now(timezone.utc).isoformat()
    commands = {
        "admission": [python, "formal/check_admission.py", "--lean", lean,
                      "--output", str(out / "admission")],
        "provider_contract": [python, "formal/check_stripe_gate.py", "--lean", lean,
                              "--output", str(out / "provider_contract")],
        "baseline": [python, "-m", "trustbound.closure_experiment",
                     "--output", str(out / "baseline")],
        "baseline_tests": [python, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "tests/test_closure_experiment.py",
                           "--junitxml", str(out / "baseline-tests.xml")],
    }
    (out / "run-input.json").write_text(json.dumps({
        "started_at_utc": started, "python_version": sys.version,
        "platform": platform.platform(), "commands": commands,
        "cwd": str(snapshot), "environment_keys": sorted(env),
        "sources_sha256": hashes, "runner_sha256": digest(Path(__file__)),
        "scope": "selected core only; existing local toolchains; no provider calls",
    }, indent=2) + "\n")

    def execute(item):
        name, command = item
        begin = time.monotonic()
        try:
            result = subprocess.run(command, cwd=snapshot, env=env,
                                    capture_output=True, text=True, timeout=240)
            code, log = result.returncode, result.stdout + result.stderr
        except Exception as exc:
            code, log = -1, repr(exc)
        (out / (name + ".log")).write_text(log)
        print(f"{name}: exit {code}", flush=True)
        return name, {"exit_code": code, "seconds": time.monotonic() - begin}

    print("Running selected sources from a fresh snapshot", flush=True)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = dict(pool.map(execute, commands.items()))
    report = {
        "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs, "sources_sha256": hashes,
        "snapshot_matches_current_sources": all(digest(root / n) == h for n, h in hashes.items()),
        "checks_passed": False, "provider_requests": 0, "new_theorems": 0,
        "full_regression_suite_run": False, "new_dependencies_installed": False,
        "limitations": "Conditional models and finite synthetic baseline; no provider/source refinement or novelty result. Existing Python and Lean environments reused.",
    }
    try:
        assert all(job["exit_code"] == 0 for job in jobs.values()), jobs
        assert report["snapshot_matches_current_sources"]
        admission = json.loads((out / "admission/summary.json").read_text())
        contract = json.loads((out / "provider_contract/summary.json").read_text())
        result = json.loads((out / "baseline/closure_benchmark.json").read_text())
        assert len(admission["exported_theorems"]) == 8
        assert len(contract["exported_theorems"]) == 6
        mutations = list(admission["mutations"].values()) + list(contract["mutations"].values())
        assert len(mutations) == 8 and all(m["proof_rejected"] for m in mutations)
        records = result["records"]
        assert len(records) == 2048
        # Recount all verdicts from saved records, independently of the summary.
        for config, scopes in result["summary"].items():
            for scope, held in (("assumptions_hold", True), ("bypass_violation", False)):
                subset = [x for x in records if x["configuration"] == config and x["assumptions_hold"] == held]
                expected = scopes[scope]
                assert expected["traces"] == len(subset) == 256
                for key in ("coverage_accepted", "exact_accepted", "false_coverage", "false_exact"):
                    assert expected[key] == sum(x[key] for x in subset)
        # Compare each state's public input and verdict, not just aggregate totals.
        for start in range(0, len(records), 4):
            arms = records[start:start + 4]
            assert len({json.dumps(x["evidence"], sort_keys=True) for x in arms}) == 1
            strong = {x["configuration"]: x for x in arms}
            for key in ("coverage_accepted", "exact_accepted"):
                assert strong["fenced_reconciliation"][key] == strong["conventional_reconciliation"][key]
        historical = root / "results/evidence_only_2026-11-01/closure_benchmark.json"
        assert result == json.loads(historical.read_text())
        suites = list(ET.parse(out / "baseline-tests.xml").getroot().iter("testsuite"))
        counts = {k: sum(int(s.get(k, "0")) for s in suites) for k in ("tests", "failures", "errors", "skipped")}
        assert counts == {"tests": 9, "failures": 0, "errors": 0, "skipped": 0}, counts
        report.update({
            "checks_passed": True, "lean": admission["lean"],
            "exported_results_checked": 14, "premise_removal_mutations_rejected": 8,
            "baseline_test_counts": counts, "baseline_records": len(records),
            "same_public_evidence_groups_checked": len(records) // 4,
            "per_state_strong_baseline_tie": True, "historical_result_semantically_equal": True,
            "baseline_summary": result["summary"],
            "baseline_sha256": digest(out / "baseline/closure_benchmark.json"),
            "historical_baseline_sha256": digest(historical),
        })
    except Exception as exc:
        report["verification_error"] = repr(exc)
    report["logs_sha256"] = {str(p.relative_to(out)): digest(p) for p in out.rglob("*.log")}
    (out / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report.get(k) for k in ("checks_passed", "exported_results_checked",
          "premise_removal_mutations_rejected", "baseline_test_counts", "baseline_records",
          "per_state_strong_baseline_tie", "verification_error")}), flush=True)
    raise SystemExit(0 if report["checks_passed"] else 1)


if __name__ == "__main__":
    main()
