"""Check crash/dispatch model with pinned Lean; no provider requests."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lean", default="lean")
    p.add_argument("--output", type=Path, default=Path("results/formal_dispatch"))
    args = p.parse_args()
    source = Path(__file__).with_name("Dispatch.lean")
    code = source.read_text()
    stripped = re.sub(r"/-.*?-/|--[^\n]*", "", code, flags=re.S)
    assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    version = subprocess.run([args.lean, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    assert "version 4.19.0," in version
    args.output.mkdir(parents=True, exist_ok=True)
    checked = subprocess.run([args.lean, str(source)], capture_output=True, text=True)
    log = checked.stdout + checked.stderr
    (args.output / "dispatch-check.log").write_text(log)
    assert checked.returncode == 0 and not any(x in log for x in ("error:", "warning:", "sorryAx"))
    exports = re.findall(r"'TrustBoundDispatch\.([^']+)'", log)
    assert exports == ["reachable_safe", "dispatch_at_most_once", "dispatch_has_durable_claim",
                       "fence_survives_crashes", "crash_can_abandon_unsent_command",
                       "identical_recovery_state_can_hide_send", "credential_holder_bypasses_fence"]
    for deps in re.findall(r"depends on axioms: \[([^]]*)\]", log):
        assert set(deps.split(", ")) <= {"propext", "Quot.sound"}
    mutations = {
        "reclaim_durable_command": ("(unused : id ∉ s.claimed)", "(unused : True)"),
        "send_without_ticket": ("(ticket : s.ticket = some id)", "(ticket : True)"),
        "crash_forgets_claims": (
            "| crash (s : State) : Step s { s with ticket := none }",
            "| crash (s : State) : Step s { s with ticket := none, claimed := [] }"),
        "reuse_send_ticket": (
            "Step s { s with ticket := none, sent := id :: s.sent }",
            "Step s { s with sent := id :: s.sent }"),
    }
    outcomes = {}
    with tempfile.TemporaryDirectory(prefix="dispatch-lean-") as temp:
        for name, (before, after) in mutations.items():
            assert code.count(before) == 1
            path = Path(temp) / (name + ".lean")
            path.write_text(code.replace(before, after))
            trial = subprocess.run([args.lean, str(path)], capture_output=True, text=True)
            output = (trial.stdout + trial.stderr).replace(str(path), path.name)
            (args.output / (name + ".log")).write_text(output)
            assert trial.returncode != 0 and "error:" in output
            outcomes[name] = {"proof_rejected": True, "exit_code": trial.returncode}
    summary = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "lean": version,
               "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "check_exit_code": checked.returncode, "exported_theorems": exports,
               "mutations": outcomes, "scope": "single-worker abstract dispatch under atomic durable storage and trusted nonretrying transport; not provider effects or implementation refinement"}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
