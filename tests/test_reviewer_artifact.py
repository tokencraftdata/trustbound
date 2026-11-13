"""Exercise artifact reproducibility and detection of altered or incomplete inputs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.build_reviewer_artifact import FILES, VERSION, build_archive, verify_manifest
from scripts.reproduce_reviewer_artifact import run_job
from research.support import write_report

ROOT = Path(__file__).resolve().parents[1]


def test_archive_is_reproducible_and_contains_only_selected_files(tmp_path):
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    build_archive(ROOT, first)
    build_archive(ROOT, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == set(FILES) | {"README.md", "ARTIFACT_MANIFEST.json"}
        archive.extractall(tmp_path / "extracted")
    assert verify_manifest(tmp_path / "extracted")["artifact_version"] == VERSION


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


@pytest.mark.parametrize("exit_code", [0, 3])
def test_job_preserves_both_streams_and_failure_status(tmp_path, exit_code):
    records = {}
    command = ["-c", f"import sys; print('output'); print('diagnostic', file=sys.stderr); sys.exit({exit_code})"]
    if exit_code:
        with pytest.raises(RuntimeError, match="probe failed"):
            run_job("probe", command, tmp_path, dict(os.environ), records)
    else:
        run_job("probe", command, tmp_path, dict(os.environ), records)
    assert records["probe"]["exit_code"] == exit_code
    log = (tmp_path / "probe.log").read_text()
    assert "output" in log and "diagnostic" in log


def test_job_timeout_preserves_partial_diagnostics(tmp_path):
    records = {}
    command = ["-c", "import sys,time; print('started', flush=True); print('waiting', file=sys.stderr, flush=True); time.sleep(10)"]
    with pytest.raises(RuntimeError, match="probe timed out"):
        run_job("probe", command, tmp_path, dict(os.environ), records, timeout=1)
    log = (tmp_path / "probe.log").read_text()
    assert "started" in log and "waiting" in log
    assert records["probe"]["timed_out"]
    assert records["probe"]["exit_code"] is None


def test_experiment_failure_keeps_diagnostic_prefix(tmp_path):
    path = tmp_path / "result.json"
    def fail():
        raise ValueError('{"history": ["grant", "fence"], "error": "broken"}')
    with pytest.raises(ValueError, match="broken"):
        write_report(path, fail)
    report = json.loads(path.read_text())
    assert not report["checks_passed"]
    assert json.loads(report["error"])["history"] == ["grant", "fence"]


def test_existing_report_is_never_overwritten_or_rerun(tmp_path):
    path = tmp_path / "result.json"
    expected = {"checks_passed": True, "cases": ["original"]}
    assert write_report(path, lambda: expected) == expected
    def should_not_run():
        pytest.fail("existing evidence must be preserved before starting a run")
    with pytest.raises(FileExistsError):
        write_report(path, should_not_run)
    assert json.loads(path.read_text()) == expected
