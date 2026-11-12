"""Tampering tests for finite trace evidence; no payment provider or Lean required."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys

import pytest

from research.service_refinement.check_traces import scenarios
from trustbound.trace_evidence import TraceAuditError, audit_trace, audit_traces


@pytest.fixture(scope="module")
def traces(tmp_path_factory):
    return scenarios(tmp_path_factory.mktemp("trace-audit"))


def test_executed_histories_match_declared_scenarios(traces):
    report = audit_traces(traces)
    assert report["checks_passed"]
    assert sum(case["steps"] for case in report["scenarios"]) == 66
    assert sum(case["resolved"] for case in report["scenarios"]) == 5


@pytest.mark.parametrize("tampering", [
    "missing_step", "unknown_event", "wrong_mapping", "missing_command",
    "missing_journal_row", "unmapped_object", "missing_effect", "rewritten_history",
    "forgotten_right", "false_resolution", "changed_final_snapshot", "unlogged_claim",
    "duplicate_identity", "deployment_claim",
])
def test_incomplete_or_inconsistent_evidence_is_rejected(traces, tampering):
    trace = deepcopy(next(item for item in traces if item["name"] == "claim_abandoned_before_send"))
    if tampering in {"missing_effect", "rewritten_history"}:
        trace = deepcopy(next(item for item in traces if item["name"] == "capture_across_fence"))
    if tampering == "missing_step":
        del trace["steps"][2]
    elif tampering == "unknown_event":
        trace["steps"][0]["source_event"] = "unmodeled_activation"
    elif tampering == "wrong_mapping":
        trace["steps"][2]["model_step"] = "waitOrReject"
    elif tampering == "missing_command":
        trace["steps"][2]["service_snapshot"]["commands"] = []
    elif tampering == "missing_journal_row":
        trace["steps"][1]["service_snapshot"]["records"] = []
    elif tampering == "unmapped_object":
        trace["steps"][0]["provider_objects"].append(["pi_Hidden", "requires_payment_method"])
    elif tampering == "missing_effect":
        step = next(step for step in trace["steps"] if step["model_step"] == "paid")
        step["provider_events"] = []
    elif tampering == "rewritten_history":
        trace["steps"][-1]["provider_events"] = [["canceled", "pi_Trace1"]]
    elif tampering == "forgotten_right":
        trace["states"][-1]["rights"] = []
    elif tampering == "false_resolution":
        trace["claims_resolved"] = True
    elif tampering == "changed_final_snapshot":
        trace["final_snapshot"]["closed"] = False
    elif tampering == "unlogged_claim":
        trace["steps"][2]["service_snapshot"]["commands"][0]["claimed"] = 1
    elif tampering == "duplicate_identity":
        trace["identity_map"]["pi_Alias"] = 1
    elif tampering == "deployment_claim":
        trace["steps"][-1]["service_snapshot"]["deployment_completeness_proved"] = True
    with pytest.raises(TraceAuditError):
        audit_trace(trace)


def test_missing_or_duplicate_scenario_is_rejected(traces):
    for changed in (traces[:-1], [traces[0]] * len(traces)):
        with pytest.raises(TraceAuditError):
            audit_traces(changed)


def test_audit_still_rejects_under_python_optimization():
    result = subprocess.run(
        [sys.executable, "-O", "-c", "from trustbound.trace_evidence import audit_traces; audit_traces([])"],
        capture_output=True, text=True, env=os.environ.copy(),
    )
    assert result.returncode != 0
    assert "TraceAuditError" in result.stderr


@pytest.mark.parametrize("checker", [
    "scripts/reproduce_core_claim.py", "formal/check_admission.py",
    "formal/check_stripe_gate.py", "research/service_refinement/check_traces.py",
])
def test_assertion_based_checkers_refuse_optimized_execution(checker):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-O", str(root / checker), "--help"],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "Assertions must be enabled" in result.stderr
