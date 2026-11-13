"""Check the constrained provider CONTRACT model, not Stripe's implementation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    if not __debug__:
        raise SystemExit("Assertions must be enabled; do not use python -O or PYTHONOPTIMIZE.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", default="lean")
    parser.add_argument("--output", type=Path, default=Path("results/formal_stripe_gate"))
    args = parser.parse_args()
    source = Path(__file__).with_name("StripeGate.lean")
    dependency = source.with_name("Admission.lean")
    code = source.read_text()
    for p in (source, dependency):
        stripped = re.sub(r"/-.*?-/|--[^\n]*", "", p.read_text(), flags=re.S)
        assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    version = subprocess.run([args.lean, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    assert "version 4.19.0," in version
    args.output.mkdir(parents=True, exist_ok=True)
    exports = ["provider_step_refines", "provider_runs_refine", "unregistered_objects_inert",
               "fenced_provider_coverage", "terminal_manifest_drains", "terminal_cut_stable"]
    mutations = {
        "effectful_unknown_creation": (
            "ApiStep s { s with objects := id :: s.objects }",
            "ApiStep s { s with objects := id :: s.objects, core := { s.core with effects := id :: s.core.effects } }"),
        "unregistered_dispatch": ("(recorded : id ∈ s.core.journal)", "(recorded : True)"),
        "dispatch_after_terminal": ("(notTerminal : id ∉ s.terminal)", "(notTerminal : True)"),
        "cancel_without_source_discharge": (
            "rights := s.core.rights.filter (· != id) } }",
            "rights := s.core.rights } }"),
    }
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix="stripe-contract-") as temp:
        env = dict(os.environ, LEAN_PATH=temp)
        compiled = subprocess.run([args.lean, "-o", str(Path(temp) / "Admission.olean"), str(dependency)],
                                  capture_output=True, text=True, env=env)
        dependency_log = compiled.stdout + compiled.stderr
        (args.output / "admission-dependency.log").write_text(dependency_log)
        assert compiled.returncode == 0 and not any(x in dependency_log for x in ("sorryAx", "warning:", "error:"))
        checked = subprocess.run([args.lean, str(source)], capture_output=True, text=True, env=env)
        log = checked.stdout + checked.stderr
        (args.output / "stripe-gate-check.log").write_text(log)
        assert checked.returncode == 0 and not any(x in log for x in ("sorryAx", "warning:", "error:"))
        assert re.findall(r"'TrustBoundStripeGate\.([^']+)'", log) == exports
        for deps in re.findall(r"depends on axioms: \[([^]]*)\]", log):
            assert set(deps.split(", ")) <= {"propext", "Quot.sound"}
        for name, (before, after) in mutations.items():
            assert code.count(before) == 1
            path = Path(temp) / (name + ".lean")
            path.write_text(code.replace(before, after, 1))
            trial = subprocess.run([args.lean, str(path)], capture_output=True, text=True, env=env)
            output = (trial.stdout + trial.stderr).replace(str(path), path.name)
            (args.output / (name + ".log")).write_text(output)
            rejected = trial.returncode != 0 and "error:" in output
            assert rejected, name
            outcomes[name] = {"proof_rejected": rejected, "exit_code": trial.returncode}
    summary = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "lean": version,
               "sources_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in (source, dependency, Path(__file__))},
               "check_exit_code": checked.returncode, "exported_theorems": exports,
               "mutations": outcomes, "provider_implementation_verified": False,
               "scope": "simulation between two specified transition systems; inert-create and terminal-state provider contracts plus exclusive mediation assumed"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
