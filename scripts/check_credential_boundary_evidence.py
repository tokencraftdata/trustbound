"""Summarize executed interface tests without upgrading blocked isolation to success."""
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "results/credential_boundary_2026-11-02"
    counts = {}
    retry = root / "results/credential_containers_2026-11-02"
    for filename, expected in (("interface-tests.xml", 23), ("focused-tests.xml", 43), ("full-tests.xml", 213)):
        evidence = retry / "local-tests.xml" if filename == "full-tests.xml" and (retry / "local-tests.xml").exists() else output / filename
        tree = ET.parse(evidence).getroot()
        assert len(list(tree.iter("testcase"))) == expected
        assert not any(list(tree.iter(tag)) for tag in ("failure", "error", "skipped"))
        counts[filename] = expected
    container_path = retry / "container-report.json" if (retry / "container-report.json").exists() else output / "container-report.json"
    container = json.loads(container_path.read_text())
    assert container["status"] == "blocked_runtime_unavailable"
    assert container["isolation_tests_executed"] is False
    assert container["real_provider_calls"] == 0
    files = ["src/trustbound/credential_service.py", "src/trustbound/stripe_gate.py",
             "scripts/validate_credential_containers.py", "scripts/check_credential_boundary_evidence.py",
             "scripts/run_local_docker_checks.py",
             "tests/test_credential_service.py", "tests/test_credential_boundary_runtime.py",
             "deployment/credential_boundary/adversarial_agent.py", "deployment/credential_boundary/Dockerfile"]
    for name in files:
        if name.endswith(".py"):
            ast.parse((root / name).read_text(), filename=name)
    report = {"full_tests_passed": 213, "new_focused_tests_passed": 43,
              "test_counts": counts, "isolation_tests_executed": False,
              "isolation_established": False, "real_provider_calls": 0,
              "formal_checks_rerun": False, "container_status": container["status"],
              "container_evidence": str(container_path.relative_to(root)),
              "full_test_evidence": str((retry / "local-tests.xml" if (retry / "local-tests.xml").exists() else output / "full-tests.xml").relative_to(root)),
              "positive_local_result": "fixed interface tested across a separate process",
              "negative_control": "same-user process can read synthetic secret",
              "blocker": "functioning authorized container runtime",
              "current_sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files}}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("full_tests_passed", "new_focused_tests_passed",
                                           "isolation_tests_executed", "isolation_established")}))


if __name__ == "__main__":
    main()
