"""Reproduce admission/fence proofs and premise-removal regression checks."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


EXPORTS = [
    "reachable_coverage", "fenced_population_immutable", "post_fence_coverage",
    "drained_fence_effects_stable", "reconciled_fence_complete",
    "fence_without_drain", "bypass_breaks_coverage", "refinement_transfers_coverage",
]


def main():
    if not __debug__:
        raise SystemExit("Assertions must be enabled; do not use python -O or PYTHONOPTIMIZE.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, default=Path("results/formal_admission"))
    args = parser.parse_args()
    source = Path(__file__).with_name("Admission.lean")
    code = source.read_text()
    stripped = re.sub(r"/-.*?-/|--[^\n]*", "", code, flags=re.S)
    assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    version = subprocess.run([args.lean, "--version"], capture_output=True, text=True,
                             check=True).stdout.strip()
    if "version 4.19.0," not in version:
        raise SystemExit("Use pinned Lean 4.19.0")
    args.output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([args.lean, str(source)], capture_output=True, text=True)
    log = result.stdout + result.stderr
    (args.output / "admission-check.log").write_text(log)
    if result.returncode or "sorryAx" in log or "warning:" in log:
        raise SystemExit("Proof check failed; inspect admission-check.log")
    exported = re.findall(r"'TrustBoundAdmission\.([^']+)'", log)
    assert exported == EXPORTS
    dependencies = re.findall(r"depends on axioms: \[([^]]*)\]", log)
    assert len(dependencies) == len(EXPORTS)
    for dependency in dependencies:
        assert set(dependency.split(", ")) <= {"propext", "Quot.sound"}
    # These are dependency checks on the existing proof text, not separate
    # minimality theorems. Explicit counterexecutions are checked above.
    mutations = {
        "grant_without_record": ("(recorded : id ∈ s.journal)", "(recorded : True)"),
        "record_after_fence": (
            "| record (s : State) (id : Nat) (isOpen : s.closed = false)",
            "| record (s : State) (id : Nat) (isOpen : True)"),
        "grant_after_fence": (
            "| grant (s : State) (id : Nat) (isOpen : s.closed = false)",
            "| grant (s : State) (id : Nat) (isOpen : True)"),
        "deliver_without_right": ("(authorized : id ∈ s.rights)", "(authorized : True)"),
    }
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix="trustbound-admission-") as temp:
        for name, (before, after) in mutations.items():
            assert code.count(before) == 1
            path = Path(temp) / (name + ".lean")
            path.write_text(code.replace(before, after, 1))
            checked = subprocess.run([args.lean, str(path)], capture_output=True, text=True)
            output = (checked.stdout + checked.stderr).replace(str(path), path.name)
            (args.output / (name + ".log")).write_text(output)
            rejected = checked.returncode != 0 and "error:" in output
            outcomes[name] = {"proof_rejected": rejected, "exit_code": checked.returncode}
            if not rejected:
                raise SystemExit("Mutation unexpectedly accepted: " + name)
    summary = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "lean": version,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "check_exit_code": result.returncode,
        "exported_theorems": exported,
        "axioms_by_theorem": dict(zip(exported, [d.split(", ") for d in dependencies])),
        "mutations": outcomes,
        "scope": "one path/epoch; conditional identity coverage and drain stability; no provider or Python refinement, monetary accounting, cryptography or liveness",
        "api_calls_this_check": 0,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
