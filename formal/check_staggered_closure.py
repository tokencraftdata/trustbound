"""Check accumulation of irreversible observations in the provider contract model."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lean", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    sources = [here / (name + ".lean") for name in
               ("Admission", "StripeGate", "StaggeredClosure")]
    for source in sources:
        stripped = re.sub(r"/-.*?-/|--[^\n]*", "", source.read_text(), flags=re.S)
        assert not re.search(r"\b(sorry|axiom|unsafe|native_decide)\b", stripped)
    version = subprocess.run([args.lean, "--version"], capture_output=True,
                             text=True, check=True).stdout.strip()
    assert "version 4.19.0," in version
    args.output.mkdir(parents=True, exist_ok=True)
    exports = ["accumulate_stable_observations", "terminal_persists",
               "staggered_terminal_closure"]
    with tempfile.TemporaryDirectory(prefix="staggered-closure-") as temp:
        env = dict(os.environ, LEAN_PATH=temp)
        for source in sources:
            command = [args.lean]
            if source != sources[-1]:
                command += ["-o", str(Path(temp) / (source.stem + ".olean"))]
            checked = subprocess.run(command + [str(source)], capture_output=True,
                                     text=True, env=env)
            log = checked.stdout + checked.stderr
            (args.output / (source.stem + ".log")).write_text(log)
            assert checked.returncode == 0, log
            assert not any(token in log for token in ("sorryAx", "warning:", "error:")), log
            for deps in re.findall(r"depends on axioms: \[([^]]*)\]", log):
                assert set(deps.split(", ")) <= {"propext", "Quot.sound"}, deps
        assert re.findall(r"'TrustBoundStaggeredClosure\.([^']+)'", log) == exports
    summary = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "lean": version, "exit_code": 0,
        "new_exports_checked": exports,
        "dependencies_recompiled": ["Admission", "StripeGate"],
        "sources_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sources + [Path(__file__)]},
        "novelty_established": False,
        "interpretation": "Generic stable-fact accumulation instantiated for the existing provider contract; semantic observations and terminality are assumed.",
        "new_provider_requests": 0, "new_runtime_tests": 0,
        "implementation_verified": False,
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
