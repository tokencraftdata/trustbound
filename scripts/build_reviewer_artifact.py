"""Build a deterministic, versioned reviewer ZIP from an explicit source list."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.0-review.3"
FILES = (
    "RIGHTS_PENDING.txt", "requirements-reviewer.txt", "requirements-core.txt",
    "docs/REVIEWER_GUIDE.md", "docs/RESEARCH_CONTRACT.md", "docs/CORRECTNESS_FIXES.md",
    "formal/lean-toolchain", "formal/Admission.lean", "formal/StripeGate.lean",
    "formal/check_admission.py", "formal/check_stripe_gate.py",
    "src/trustbound/__init__.py", "src/trustbound/closure_experiment.py",
    "src/trustbound/stripe_gate.py", "src/trustbound/credential_service.py",
    "src/trustbound/trace_evidence.py",
    "scripts/reproduce_core_claim.py", "scripts/reproduce_reviewer_artifact.py",
    "scripts/build_reviewer_artifact.py", "scripts/check_trace_evidence.py",
    "research/service_refinement/check_traces.py",
    "research/service_refinement/check_schedules.py", "tests/test_generated_schedules.py",
    "research/agent_behaviors/evaluate.py", "research/agent_behaviors/README.md",
    "research/agent_behaviors/evidence/results.json", "tests/test_agent_behaviors.py",
    "research/service_refinement/evidence/traces.json",
    "results/evidence_only_2026-11-01/closure_benchmark.json",
    "tests/test_closure_experiment.py", "tests/test_stripe_gate.py",
    "tests/test_gate_observation_integrity.py", "tests/test_credential_service.py",
    "tests/test_dispatch_crashes.py", "tests/dispatch_crash_worker.py",
    "tests/test_trace_evidence.py", "tests/test_reviewer_artifact.py",
)
README = """# TrustBound reviewer artifact

This package contains a conditional payment model and finite local checks.
Start with [the reviewer guide](docs/REVIEWER_GUIDE.md) for setup, expected
results, scenario descriptions, and the limits of the evidence.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-reviewer.txt
.venv/bin/python scripts/reproduce_reviewer_artifact.py \\
  --lean /absolute/path/to/lean-4.19.0/bin/lean --output results/reviewer-run
```

Use a new output directory. Lean 4.19.0 must be installed separately.
No provider credentials, SDKs, real payments, or network are needed after setup.
See RIGHTS_PENDING.txt for the existing licensing status. This review package
does not grant a license or imply a public release, DOI, or independent review.
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(hashes: dict[str, str]) -> str:
    return sha256(json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode())


def verify_manifest(root: Path) -> dict:
    """Verify the exact selected input list and its hashes, not its provenance."""
    manifest = json.loads((root / "ARTIFACT_MANIFEST.json").read_text())
    hashes = manifest["files_sha256"]
    if set(hashes) != set(FILES) | {"README.md"}:
        raise ValueError("artifact file list does not match the selected reviewer inputs")
    if manifest["content_id"] != content_id(hashes):
        raise ValueError("artifact content ID mismatch")
    for name, expected in hashes.items():
        path = root / name
        if path.is_symlink() or sha256(path.read_bytes()) != expected:
            raise ValueError(f"artifact checksum mismatch: {name}")
    return manifest


def build_archive(root: Path, output: Path, version: str = VERSION) -> dict:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9][A-Za-z0-9.-]*)?", version):
        raise ValueError("invalid artifact version")
    if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
        raise FileExistsError("use a new archive output path")
    members = {name: (root / name).read_bytes() for name in FILES}
    members["README.md"] = README.encode()
    hashes = {name: sha256(data) for name, data in sorted(members.items())}
    manifest = {
        "schema_version": 1, "artifact_version": version,
        "content_id": content_id(hashes), "files_sha256": hashes,
        "toolchain": {"lean": "4.19.0", "python": ">=3.11", "platforms": ["Linux", "macOS"]},
        "scope": "Conditional models and selected local simulator histories; no deployment certification.",
    }
    members["ARTIFACT_MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w") as archive:
        for name, data in sorted(members.items()):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data, compresslevel=9)
    digest = sha256(output.read_bytes())
    with output.with_suffix(output.suffix + ".sha256").open("x") as checksum:
        checksum.write(f"{digest}  {output.name}\n")
    return {"archive": str(output), "sha256": digest, "content_id": manifest["content_id"],
            "artifact_version": version, "files": len(members)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args()
    print(json.dumps(build_archive(ROOT, args.output, args.version), indent=2))


if __name__ == "__main__":
    main()
