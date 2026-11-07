"""Exhaustive finite sanity check of Observers.lean, not payment simulation.

The certificate verifier sees only required signer slots and received positive
reports. Truth, visibility and corruption are used ONLY by the offline grader.
Bit o * paths + p names observer o's attestation for path p.
"""
import argparse
import hashlib
import json
from pathlib import Path


def accepts(required: int, reports: int) -> bool:
    return required & reports == required


def faithful(reports: int, observes: int, corrupt: int, good: int,
             observers: int, paths: int) -> bool:
    for o in range(observers):
        if corrupt & (1 << o):
            continue
        for p in range(paths):
            bit = 1 << (o * paths + p)
            if reports & observes & bit and not good & (1 << p):
                return False
    return True


def covered(required: int, observes: int, corrupt: int,
            observers: int, paths: int) -> bool:
    return all(any(required & observes & (1 << (o * paths + p))
                   and not corrupt & (1 << o) for o in range(observers))
               for p in range(paths))


def enumerate_model(observers: int = 2, paths: int = 2) -> dict:
    slots = 1 << (observers * paths)
    all_good = (1 << paths) - 1
    records = []
    valuations = 0
    mismatches = 0
    for required in range(slots):
        for observes in range(slots):
            for corrupt in range(1 << observers):
                counterexample = None
                for good in range(1 << paths):
                    for reports in range(slots):
                        valuations += 1
                        if (accepts(required, reports) and good != all_good
                                and faithful(reports, observes, corrupt, good, observers, paths)):
                            if counterexample is None:
                                counterexample = {"good_paths": good, "positive_reports": reports}
                coverage = covered(required, observes, corrupt, observers, paths)
                robust = counterexample is None
                mismatches += coverage != robust
                records.append({"required": required, "observes": observes,
                                "corrupt": corrupt, "coverage": coverage,
                                "robust": robust, "counterexample": counterexample})
    return {"model": "ideal authenticated positive reports at one fixed cut",
            "observers": observers, "paths": paths,
            "policy_observation_coalition_cases": len(records),
            "truth_report_valuations": valuations,
            "covered_cases": sum(row["coverage"] for row in records),
            "unsafe_cases": sum(not row["robust"] for row in records),
            "equivalence_mismatches": mismatches, "records": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = enumerate_model()
    result["source_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
    if result["equivalence_mismatches"]:
        raise SystemExit("Observer equivalence failed")


if __name__ == "__main__":
    main()
