"""Evidence-only synthetic comparison. Ground truth is used ONLY by the grader.

This replaces the 2026-10-27 oracle-contaminated benchmark. It is not a PSP
simulation or performance measurement. All arms receive identical Evidence.
"""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import asdict, dataclass
from pathlib import Path

@dataclass(frozen=True)
class Row:
    seq: int
    status: str
    amount: int


@dataclass(frozen=True)
class PathEvidence:
    path: str
    epoch: int
    fenced: bool
    highwater: int
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Evidence:
    paths: tuple[PathEvidence, ...]


CONFIGURATIONS = (
    "signed_closure", "witnessed_log", "fenced_reconciliation",
    "conventional_reconciliation",
)
REQUIRED_PATHS = ("flight", "hotel")


def decision(configuration: str, evidence: Evidence, *, exact: bool) -> bool:
    """No ground-truth, hidden-effect, or assumption-validity parameter.

    Authentication is idealized. Strong arms check the CLAIMED fence/cut;
    they cannot detect an authentically false statement about either.
    """
    if configuration not in CONFIGURATIONS:
        raise ValueError(configuration)
    paths = evidence.paths
    if len(paths) != len(REQUIRED_PATHS) or {p.path for p in paths} != set(REQUIRED_PATHS):
        return False
    for path in paths:
        if path.epoch != 1:
            return False
        if any(r.status not in {"pending", "confirmed", "released"}
               or r.amount < 0 or (r.status == "released" and r.amount != 0)
               for r in path.rows):
            return False
        if exact and any(r.status == "pending" for r in path.rows):
            return False
        if configuration in {"fenced_reconciliation", "conventional_reconciliation"}:
            if not path.fenced or path.highwater < 0:
                return False
            if tuple(r.seq for r in path.rows) != tuple(range(1, path.highwater + 1)):
                return False
    return True


def run() -> dict:
    records = []
    # (public status, public liability, hidden actual debit)
    states = (("pending", 100, 0), ("pending", 100, 75),
              ("confirmed", 75, 75), ("released", 0, 0))
    # Two independent paths, one admission each. Omitted reports, delayed
    # outcomes, open fences, and bypass effects are varied independently.
    for slots, reported, fenced, hidden in itertools.product(
        itertools.product(states, repeat=2),
        itertools.product((False, True), repeat=2),
        itertools.product((False, True), repeat=2), (False, True),
    ):
        evidence = Evidence(tuple(
            PathEvidence(name, 1, fenced[i], 1,
                         (Row(1, slots[i][0], slots[i][1]),) if reported[i] else ())
            for i, name in enumerate(REQUIRED_PATHS)
        ))
        # The threat-model label NEVER enters decision(). A bypass is inside
        # the intended economic scope but violates the mediation assumption.
        truth_coverage = not hidden and all(reported) and all(fenced)
        truth_exact = truth_coverage and all(s[0] != "pending" for s in slots)
        for configuration in CONFIGURATIONS:
            coverage = decision(configuration, evidence, exact=False)
            exact = decision(configuration, evidence, exact=True)
            records.append({
                "configuration": configuration, "evidence": asdict(evidence),
                "assumptions_hold": not hidden, "hidden_bypass_effect": hidden,
                "actual_debits": [s[2] for s in slots] + ([75] if hidden else []),
                "coverage_accepted": coverage, "exact_accepted": exact,
                "coverage_true": truth_coverage, "exact_true": truth_exact,
                "false_coverage": coverage and not truth_coverage,
                "false_exact": exact and not truth_exact,
            })
    summary = {}
    for configuration in CONFIGURATIONS:
        subset = [r for r in records if r["configuration"] == configuration]
        summary[configuration] = {}
        for scope, held in (("assumptions_hold", True), ("bypass_violation", False)):
            rows = [r for r in subset if r["assumptions_hold"] == held]
            summary[configuration][scope] = {
                "traces": len(rows),
                **{key: sum(r[key] for r in rows) for key in
                   ("coverage_accepted", "exact_accepted", "false_coverage", "false_exact")},
            }
    return {
        "metadata": {
            "model": "evidence-only two-path bounded model v2",
            "synthetic": True,
            "supersedes": "2026-10-27 oracle-contaminated closure counts; withdrawn",
            "claim_scope": "conditional coverage and exact closure; no live rail",
            "enumeration": "4^2 lifecycle states x 2^2 report masks x 2^2 fence masks x 2 bypass states",
            "authentication": "idealized; no cryptographic performance claim",
        },
        "summary": summary,
        "records": records,
    }


def write(result: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "closure_benchmark.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    result = run()
    write(result, args.output)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
