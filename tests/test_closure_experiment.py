from dataclasses import replace
import inspect

from trustbound.closure_experiment import (
    CONFIGURATIONS, Evidence, PathEvidence, Row, decision, run,
)


def test_fenced_and_conventional_reconciliation_tie():
    result = run()["summary"]
    assert result["fenced_reconciliation"] == result["conventional_reconciliation"]


def test_witnessing_alone_does_not_fix_hidden_effects():
    result = run()["summary"]
    assert result["witnessed_log"]["bypass_violation"]["false_exact"] > 0


def test_fenced_scope_has_no_false_valid_in_bounded_model():
    result = run()["summary"]
    assert result["fenced_reconciliation"]["assumptions_hold"]["false_exact"] == 0
    assert result["fenced_reconciliation"]["assumptions_hold"]["false_coverage"] == 0


def complete_evidence():
    return Evidence(tuple(PathEvidence(p, 1, True, 1, (Row(1, "confirmed", 75),))
                          for p in ("flight", "hotel")))


def test_no_hidden_or_ground_truth_argument():
    assert tuple(inspect.signature(decision).parameters) == ("configuration", "evidence", "exact")


def test_same_evidence_same_decision_even_when_bypass_exists():
    records = [r for r in run()["records"] if r["configuration"] == "fenced_reconciliation"]
    for clean, hidden in zip(records[::2], records[1::2]):
        assert clean["evidence"] == hidden["evidence"]
        assert clean["exact_accepted"] == hidden["exact_accepted"]
        assert clean["coverage_accepted"] == hidden["coverage_accepted"]
    assert any(r["false_exact"] for r in records)


def test_uncertainty_is_covered_but_not_exact():
    evidence = complete_evidence()
    first = replace(evidence.paths[0], rows=(Row(1, "pending", 100),))
    evidence = Evidence((first, evidence.paths[1]))
    assert decision("fenced_reconciliation", evidence, exact=False)
    assert not decision("fenced_reconciliation", evidence, exact=True)


def test_stale_duplicate_missing_and_gap_evidence_rejected():
    evidence = complete_evidence()
    bad_vectors = (
        evidence.paths[:1],
        (evidence.paths[0], evidence.paths[0]),
        (replace(evidence.paths[0], epoch=0), evidence.paths[1]),
        (replace(evidence.paths[0], rows=()), evidence.paths[1]),
        (replace(evidence.paths[0], fenced=False), evidence.paths[1]),
    )
    for vector in bad_vectors:
        assert not decision("fenced_reconciliation", Evidence(vector), exact=True)


def test_authentic_false_cut_is_not_magically_detectable():
    # A compromised sole source can claim highwater zero, concealing admission.
    evidence = complete_evidence()
    false_cut = replace(evidence.paths[0], highwater=0, rows=())
    assert decision("fenced_reconciliation", Evidence((false_cut, evidence.paths[1])), exact=True)


def test_symbolic_denominators_and_fair_strong_baseline():
    result = run()
    assert len(result["records"]) == 512 * len(CONFIGURATIONS)
    for summary in result["summary"].values():
        assert summary["assumptions_hold"]["traces"] == 256
        assert summary["bypass_violation"]["traces"] == 256
