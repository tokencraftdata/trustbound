"""Run the formal core, service tests and trace audits with one local command."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

from build_reviewer_artifact import FILES, verify_manifest

ROOT = Path(__file__).resolve().parents[1]
SERVICE_TESTS = (
    "tests/test_gate_observation_integrity.py", "tests/test_stripe_gate.py",
    "tests/test_dispatch_crashes.py", "tests/test_credential_service.py",
    "tests/test_trace_evidence.py", "tests/test_reviewer_artifact.py",
    "tests/test_generated_schedules.py",
    "tests/test_agent_behaviors.py",
)


def main():
    if not __debug__:
        raise SystemExit("Assertions must be enabled; do not use python -O or PYTHONOPTIMIZE.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.version_info < (3, 11) or sys.platform not in {"linux", "darwin"}:
        raise SystemExit("The reviewer workflow requires Python 3.11+ on Linux or macOS.")
    dependencies = {}
    for line in (ROOT / "requirements-reviewer.txt").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==")
        actual = importlib.metadata.version(name)
        if actual != expected:
            raise SystemExit(f"Install requirements-reviewer.txt: {name} must be {expected}, found {actual}")
        dependencies[name] = actual
    lean = args.lean.resolve()
    version = subprocess.run([str(lean), "--version"], capture_output=True, text=True,
                             check=True, timeout=30).stdout.strip()
    if "version 4.19.0," not in version:
        raise SystemExit("Use pinned Lean 4.19.0")
    manifest = verify_manifest(ROOT) if (ROOT / "ARTIFACT_MANIFEST.json").exists() else None
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source_hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    report = {
        "checks_passed": False, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "platform": platform.platform(), "lean": version,
        "dependencies": dependencies, "source_sha256": source_hashes,
        "artifact_content_id": manifest["content_id"] if manifest else None,
        "jobs": {}, "provider_requests": 0,
        "universal_implementation_refinement": False, "deployment_assumptions_established": False,
        "scope": "Conditional model proofs, selected service tests, bounded schedules, scripted request-only agent behaviors and finite supplied-evidence consistency checks.",
    }
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONNOUSERSITE="1",
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
    jobs = {
        "core": ["scripts/reproduce_core_claim.py", "--lean", str(lean), "--output", str(output / "core")],
        "service_tests": ["-m", "pytest", "-q", "-p", "no:cacheprovider", *SERVICE_TESTS,
                          "--junitxml", str(output / "service-tests.xml")],
        "traces": ["research/service_refinement/check_traces.py", "--lean", str(lean),
                   "--output", str(output / "traces")],
        "exported_trace_audit": ["scripts/check_trace_evidence.py", "--traces",
                                 str(output / "traces/traces.json"), "--output", str(output / "exported-trace-audit.json")],
        "reference_trace_audit": ["scripts/check_trace_evidence.py", "--traces",
                                  "research/service_refinement/evidence/traces.json", "--output",
                                  str(output / "reference-trace-audit.json")],
        "generated_schedules": ["research/service_refinement/check_schedules.py", "--output",
                                str(output / "generated-schedules.json")],
        "agent_behaviors": ["research/agent_behaviors/evaluate.py", "--output",
                            str(output / "agent-behaviors.json")],
    }
    try:
        for name, arguments in jobs.items():
            command = [sys.executable, *arguments]
            result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
            (output / f"{name}.log").write_text(result.stdout + result.stderr)
            report["jobs"][name] = {"command": command, "exit_code": result.returncode}
            print(f"{name}: exit {result.returncode}", flush=True)
            if result.returncode:
                raise RuntimeError(f"{name} failed; inspect {name}.log")
        core = json.loads((output / "core/summary.json").read_text())
        traces = json.loads((output / "traces/summary.json").read_text())
        schedules = json.loads((output / "generated-schedules.json").read_text())
        agents = json.loads((output / "agent-behaviors.json").read_text())
        if schedules["checks_passed"] is not True or schedules["generated_cases"] != 864:
            raise RuntimeError("incomplete generated schedule run")
        if core["checks_passed"] is not True or traces["checks_passed"] is not True:
            raise RuntimeError("a component did not report successful checks")
        if agents["checks_passed"] is not True or agents["generated_cases"] != 40:
            raise RuntimeError("incomplete agent behavior run")
        suites = list(ET.parse(output / "service-tests.xml").getroot().iter("testsuite"))
        counts = {key: sum(int(suite.get(key, "0")) for suite in suites)
                  for key in ("tests", "failures", "errors", "skipped")}
        if counts["tests"] < 138 or any(counts[key] for key in ("failures", "errors", "skipped")):
            raise RuntimeError(f"incomplete service test run: {counts}")
        if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest
               for name, digest in source_hashes.items()):
            raise RuntimeError("selected sources changed during the run")
        report.update({
            "checks_passed": True, "service_test_counts": counts,
            "generated_schedule_results": {key: schedules[key] for key in (
                "generated_cases", "resolved_cases", "unresolved_cases")},
            "agent_behavior_results": {key: agents[key] for key in (
                "generated_cases", "resolved_after_agent", "resolved_after_operator",
                "pending_after_operator", "max_capture_invocations_per_case", "max_paid_effects_per_case")},
            "core_results": {key: core[key] for key in (
                "exported_results_checked", "premise_removal_mutations_rejected", "baseline_records", "baseline_test_counts")},
            "trace_results": {key: traces[key] for key in (
                "executed_service_traces", "projected_steps", "closed_trace_instances",
                "unresolved_trace_instances", "invalid_trace_inputs_rejected", "projection_audit_passed")},
        })
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    report["logs_sha256"] = {str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in output.rglob("*.log")}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report.get(key) for key in ("checks_passed", "core_results", "service_test_counts", "trace_results", "generated_schedule_results", "agent_behavior_results", "error")}))
    raise SystemExit(0 if report["checks_passed"] else 1)


if __name__ == "__main__":
    main()
