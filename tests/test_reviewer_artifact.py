"""Exercise artifact reproducibility and detection of altered or incomplete inputs."""
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.build_reviewer_artifact import FILES, build_archive, verify_manifest

ROOT = Path(__file__).resolve().parents[1]


def test_archive_is_reproducible_and_contains_only_selected_files(tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    build_archive(ROOT, first)
    build_archive(ROOT, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == set(FILES) | {"README.md", "ARTIFACT_MANIFEST.json"}
        archive.extractall(tmp_path / "extracted")
    assert verify_manifest(tmp_path / "extracted")["artifact_version"] == "1.1.0-review.1"


@pytest.mark.parametrize("change", ["source", "missing", "manifest"])
def test_modified_artifact_is_rejected(tmp_path, change):
    archive = tmp_path / "artifact.zip"
    build_archive(ROOT, archive)
    extracted = tmp_path / "extracted"
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(extracted)
    if change == "source":
        (extracted / "formal/Admission.lean").write_text("-- altered proof\n")
    elif change == "missing":
        (extracted / "tests/test_stripe_gate.py").unlink()
    else:
        path = extracted / "ARTIFACT_MANIFEST.json"
        manifest = json.loads(path.read_text())
        del manifest["files_sha256"]["tests/test_stripe_gate.py"]
        path.write_text(json.dumps(manifest))
    with pytest.raises((ValueError, FileNotFoundError)):
        verify_manifest(extracted)


def test_builder_does_not_overwrite_an_archive(tmp_path):
    path = tmp_path / "artifact.zip"
    path.write_bytes(b"existing archive")
    with pytest.raises(FileExistsError):
        build_archive(ROOT, path)
    assert path.read_bytes() == b"existing archive"


def test_reviewer_command_refuses_optimization_before_running_jobs():
    result = subprocess.run([sys.executable, "-O", str(ROOT / "scripts/reproduce_reviewer_artifact.py"), "--help"],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert "Assertions must be enabled" in result.stderr
