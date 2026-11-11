import copy
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("container_boundary", ROOT / "scripts/validate_credential_containers.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def inspection():
    # Synthetic Docker-inspect data: tests the validator, NOT the OS boundary.
    return {"Config": {"User": "2000:2000", "Env": ["PYTHONPATH=/app"]},
            "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "NetworkMode": "none",
                           "PidMode": "", "IpcMode": "private", "CapAdd": [], "CapDrop": ["ALL"],
                           "SecurityOpt": ["no-new-privileges"], "Devices": [], "DeviceRequests": []},
            "Mounts": [{"Destination": "/run/gate", "RW": False, "Type": "volume", "Name": "socket-volume"}]}


def validate(data):
    return module.validate_inspection(data, {"/run/gate": False}, "2000:2000", {"/run/gate": "socket-volume"})


def test_expected_container_configuration_accepted():
    assert validate(inspection())["network"] == "none"


@pytest.mark.parametrize("key,value", [
    ("ReadonlyRootfs", False), ("Privileged", True), ("NetworkMode", "host"),
    ("PidMode", "host"), ("IpcMode", "host"), ("CapAdd", ["SYS_ADMIN"]),
    ("CapDrop", []), ("SecurityOpt", []), ("SecurityOpt", ["no-new-privileges", "seccomp=unconfined"]),
    ("GroupAdd", ["0"]), ("Devices", ["device"]), ("DeviceRequests", ["device"]),
])
def test_unsafe_container_configuration_rejected(key, value):
    data = inspection()
    data["HostConfig"][key] = value
    with pytest.raises(AssertionError):
        validate(data)


@pytest.mark.parametrize("change", ["wrong-user", "key-env", "writable-socket-mount", "host-bind", "wrong-volume", "extra-mount"])
def test_credential_and_mount_leaks_rejected(change):
    data = inspection()
    if change == "wrong-user": data["Config"]["User"] = "0:0"
    if change == "key-env": data["Config"]["Env"].append("STRIPE_TEST_KEY=not-a-real-key")
    if change == "writable-socket-mount": data["Mounts"][0]["RW"] = True
    if change == "host-bind": data["Mounts"][0]["Type"] = "bind"
    if change == "wrong-volume": data["Mounts"][0]["Name"] = "secret-volume"
    if change == "extra-mount": data["Mounts"].append({"Destination": "/var/run/docker.sock", "RW": True, "Type": "bind"})
    with pytest.raises(AssertionError):
        validate(data)


def test_separate_process_rpc_is_not_same_user_isolation():
    # Short path for macOS AF_UNIX. Uses a synthetic canary, never a provider key.
    with tempfile.TemporaryDirectory(prefix="ipc-", dir=os.environ.get("TMPDIR")) as directory:
        root = Path(directory)
        state = root / "state"
        state.mkdir()
        credential = root / "key"
        credential.write_text("TB_BOUNDARY_CANARY_PROCESS_TEST")
        credential.chmod(0o400)
        path = root / "s"
        child = subprocess.Popen([sys.executable, "-m", "trustbound.credential_service",
                                  "--socket", str(path), "--state", str(state), "--credential", str(credential)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not path.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert path.exists(), "service did not start: " + (
                child.stderr.read() if child.poll() is not None else "startup timed out")
            def rpc(request):
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.settimeout(2)
                    client.connect(str(path))
                    client.sendall(json.dumps(request).encode() + b"\n")
                    return json.loads(client.makefile("rb").readline(8192))
            assert not rpc({"op": "observe", "status": "canceled"})["ok"]
            assert rpc({"op": "dispatch", "command_id": 1})["ok"]
            assert not rpc({"op": "dispatch", "command_id": 1})["ok"]
            assert rpc({"op": "reconcile"})["result"]["known_manifest_resolved"]
            # Negative control: separate processes alone still permit key reads.
            reader = subprocess.run([sys.executable, "-c",
                "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text().startswith('TB_BOUNDARY_CANARY_'))",
                str(credential)], capture_output=True, text=True, timeout=5)
            assert reader.returncode == 0 and reader.stdout.strip() == "True"
        finally:
            child.terminate()
            child.communicate(timeout=5)
