"""Check the Lean kernel and guard-removal mutations; standard library only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, default=Path("results/formal"))
    args = parser.parse_args()
    source = Path(__file__).with_name("Closure.lean")
    code = source.read_text()
    stripped = re.sub(r"/-.*?-/|--[^\n]*", "", code, flags=re.S)
    assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    version = subprocess.run([args.lean, "--version"], text=True, capture_output=True, check=True).stdout.strip()
    if "version 4.19.0," not in version:
        raise SystemExit("Use pinned Lean 4.19.0")
    checked = subprocess.run([args.lean, str(source)], text=True, capture_output=True)
    log = checked.stdout + checked.stderr
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "lean-check.log").write_text(log)
    if checked.returncode or "sorryAx" in log or "warning:" in log:
        raise SystemExit("Proof check failed; inspect lean-check.log")
    exported = re.findall(r"'TrustBound\.([^']+)'", log)
    assert len(exported) == 8
    mutations = {
        "remove_admission_fence": ("(isOpen : s.closed = false)", "(isOpen : True)"),
        "remove_effect_cap": ("(bounded : c.actual + d ≤ c.cap)", "(bounded : True)"),
        "permit_effect_after_terminal": ("(pending : c.terminal = false)", "(pending : True)"),
    }
    mutation_results = {}
    with tempfile.TemporaryDirectory(prefix="trustbound-lean-") as temp:
        for name, (before, after) in mutations.items():
            assert before in code
            path = Path(temp) / f"{name}.lean"
            path.write_text(code.replace(before, after, 1))
            result = subprocess.run([args.lean, str(path)], text=True, capture_output=True)
            output = (result.stdout + result.stderr).replace(str(path), name + ".lean")
            (args.output / f"{name}.log").write_text(output)
            rejected = result.returncode != 0 and "error:" in output
            mutation_results[name] = {"proof_rejected": rejected, "exit_code": result.returncode}
            if not rejected:
                raise SystemExit(f"Guard mutation not rejected: {name}")
    summary = {
        "lean": version, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "check_exit_code": checked.returncode, "exported_theorems": exported,
        "axioms": "propext and Quot.sound only where listed; no sorryAx or custom axioms",
        "mutations": mutation_results,
        "scope": "abstract safety and observation boundary; no implementation refinement or liveness proof",
    }
    observer_source = source.with_name("Observers.lean")
    observer_code = observer_source.read_text()
    stripped = re.sub(r"/-.*?-/|--[^\n]*", "", observer_code, flags=re.S)
    assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    checked_observers = subprocess.run(
        [args.lean, str(observer_source)], text=True, capture_output=True)
    observer_log = checked_observers.stdout + checked_observers.stderr
    (args.output / "observer-check.log").write_text(observer_log)
    if checked_observers.returncode or "sorryAx" in observer_log or "warning:" in observer_log:
        raise SystemExit("Observer proof check failed; inspect observer-check.log")
    observer_exported = re.findall(r"'TrustBoundObservers\.([^']+)'", observer_log)
    assert observer_exported == [
        "robust_iff_coverage", "coalition_policy_iff", "derived_evidence_same",
        "no_finite_closure_under_delayed_shadow", "delayed_arrival_instance"]
    # Standard Lean logical axioms only; preserve the full per-theorem audit.
    for dependencies in re.findall(r"depends on axioms: \[([^]]*)\]", observer_log):
        assert set(dependencies.split(", ")) <= {"propext", "Classical.choice", "Quot.sound"}
    observer_mutations = {
        "ignore_observation_coverage": ("required o p ∧ observes o p ∧ ¬ corrupt o", "required o p ∧ True ∧ ¬ corrupt o"),
        "ignore_corruption_coverage": ("required o p ∧ observes o p ∧ ¬ corrupt o", "required o p ∧ observes o p ∧ True"),
        "remove_truthful_observation": ("observes o p → report o p → good p", "observes o p → report o p → True"),
        "remove_transcript_equality": ("view hidden n = view clean n ∧ ¬ complete hidden n", "True ∧ ¬ complete hidden n"),
    }
    observer_mutation_results = {}
    with tempfile.TemporaryDirectory(prefix="trustbound-observers-") as temp:
        for name, (before, after) in observer_mutations.items():
            assert before in observer_code
            path = Path(temp) / f"{name}.lean"
            path.write_text(observer_code.replace(before, after, 1))
            result = subprocess.run([args.lean, str(path)], text=True, capture_output=True)
            output = (result.stdout + result.stderr).replace(str(path), name + ".lean")
            (args.output / f"{name}.log").write_text(output)
            rejected = result.returncode != 0 and "error:" in output
            observer_mutation_results[name] = {"proof_rejected": rejected, "exit_code": result.returncode}
            if not rejected:
                raise SystemExit(f"Observer mutation not rejected: {name}")
    summary["observer_model"] = {
        "source_sha256": hashlib.sha256(observer_source.read_bytes()).hexdigest(),
        "check_exit_code": checked_observers.returncode,
        "exported_theorems": observer_exported,
        "axioms": "propext, Classical.choice and Quot.sound only where listed",
        "mutations": observer_mutation_results,
        "scope": "fixed-cut positive-report model; conditional finite-time impossibility, not provider refinement",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
