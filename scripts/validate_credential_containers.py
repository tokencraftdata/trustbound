"""Run actual isolation probes or record BLOCKED; never substitutes mocks for OS enforcement.

Builds a minimal Python image, uses only task-owned volumes, synthetic secrets,
private PID namespaces and no networking. No host filesystem bind mounts,
privileged containers, Docker-socket mounts, Stripe credentials or API calls.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid


def docker(*args, data=None, timeout=120):
    return subprocess.run(["docker", *args], input=data, capture_output=True, text=True, timeout=timeout)


def validate_inspection(info, mounts, uid, volume_names=None):
    config, host = info["Config"], info["HostConfig"]
    assert config["User"] == uid
    assert host["ReadonlyRootfs"] is True and host["Privileged"] is False
    assert host["NetworkMode"] == "none"
    assert host["PidMode"] == "" and host["IpcMode"] in ("private", "")
    assert not host.get("GroupAdd")
    assert not host.get("CapAdd") and "ALL" in [x.upper() for x in host["CapDrop"]]
    assert any(x.startswith("no-new-privileges") for x in host["SecurityOpt"])
    assert not any("unconfined" in x for x in host["SecurityOpt"])
    assert not host.get("Devices") and not host.get("DeviceRequests")
    assert {m["Destination"]: m["RW"] for m in info["Mounts"]} == mounts
    assert all(m["Type"] == "volume" for m in info["Mounts"])
    if volume_names is not None:
        assert {m["Destination"]: m["Name"] for m in info["Mounts"]} == volume_names
    assert all("STRIPE" not in entry and "TB_BOUNDARY_CANARY_" not in entry for entry in config["Env"])
    return {"user": uid, "read_only_root": True, "network": "none", "private_pid": True,
            "capabilities_dropped": "ALL", "no_new_privileges": True, "mounts": mounts,
            "privileged": False, "host_bind_mounts": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "status": "not_executed",
              "isolation_tests_executed": False, "real_provider_calls": 0,
              "provider": "local_simulator", "credential": "synthetic_canary",
              "stripe_account_exclusivity_verified": False}
    def save():
        (args.output / "container-report.json").write_text(json.dumps(report, indent=2) + "\n")
    try:
        preflight = docker("version", "--format", "{{json .Server}}", timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        report.update(status="blocked_runtime_unavailable", preflight_error=type(exc).__name__)
        save()
        print(json.dumps({"status": report["status"], "isolation_tests_executed": False}))
        return 2
    if preflight.returncode:
        report.update(status="blocked_runtime_unavailable", preflight_exit_code=preflight.returncode,
                      preflight_error=preflight.stderr.strip()[:1500])
        save()
        print(json.dumps({"status": report["status"], "isolation_tests_executed": False}))
        return 2
    report["engine"] = json.loads(preflight.stdout)
    context = args.work / ("build-" + uuid.uuid4().hex)
    context.mkdir()
    sources = {"stripe_gate.py": root / "src/trustbound/stripe_gate.py",
               "credential_service.py": root / "src/trustbound/credential_service.py",
               "adversarial_agent.py": root / "deployment/credential_boundary/adversarial_agent.py",
               "Dockerfile": root / "deployment/credential_boundary/Dockerfile"}
    for name, source in sources.items():
        shutil.copyfile(source, context / name)
    report["sources_sha256"] = {name: hashlib.sha256(source.read_bytes()).hexdigest() for name, source in sources.items()}
    tag = "trustbound-boundary:" + uuid.uuid4().hex[:12]
    built = docker("build", "--tag", tag, str(context), timeout=300)
    (args.output / "image-build.log").write_text(built.stdout + built.stderr)
    if built.returncode:
        report["status"] = "blocked_image_build"
        save()
        return 2
    image = json.loads(docker("image", "inspect", tag).stdout)[0]
    report["image_id"] = image["Id"]  # Execution uses immutable local image ID.
    identity = "tb-boundary-" + uuid.uuid4().hex[:12]
    volumes = {key: identity + "-" + key for key in ("secret", "state", "socket")}
    names = [identity + "-broker", identity + "-agent"]
    created_volumes, created_containers = [], []
    common = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
              "--pids-limit", "32", "--memory", "128m", "--cpus", "0.5", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m"]
    def mount(key, destination, readonly=False):
        return ["--mount", "type=volume,source=" + volumes[key] + ",target=" + destination + (",readonly" if readonly else "")]
    try:
        for volume in volumes.values():
            result = docker("volume", "create", volume)
            assert result.returncode == 0
            created_volumes.append(volume)
        init_code = ("import os,sys; from pathlib import Path; "
                     "p=Path('/secrets/provider-key'); p.write_text(sys.stdin.read()); "
                     "os.chmod(p,0o400); os.chown(p,1000,1000); "
                     "os.chmod('/secrets',0o700); os.chown('/secrets',1000,1000); "
                     "os.chmod('/state',0o700); os.chown('/state',1000,1000); "
                     "os.chmod('/socket',0o711); os.chown('/socket',1000,1000)")
        provision = docker("run", "--rm", "-i", "--network", "none", "--user", "0:0", "--cap-drop", "ALL",
                           "--cap-add", "CHOWN", "--security-opt", "no-new-privileges",
                           *mount("secret", "/secrets"), *mount("state", "/state"), *mount("socket", "/socket"),
                           image["Id"], "python", "-c", init_code, data="TB_BOUNDARY_CANARY_" + uuid.uuid4().hex)
        assert provision.returncode == 0, "provision_failed"
        for i, uid in enumerate(("1000:1000", "2000:2000")):
            extra = mount("socket", "/run/gate", readonly=bool(i))
            if i == 0:
                extra += mount("secret", "/run/secrets", True) + mount("state", "/state")
            command = [] if i == 0 else ["python", "/app/adversarial_agent.py"]
            created = docker("create", "--name", names[i], *common, "--user", uid, *extra, image["Id"], *command)
            assert created.returncode == 0, "container_create_failed"
            created_containers.append(names[i])
            inspected = json.loads(docker("inspect", names[i]).stdout)[0]
            report["agent_config" if i else "broker_config"] = validate_inspection(inspected,
                {"/run/gate": False} if i else {"/run/gate": True, "/run/secrets": False, "/state": True}, uid,
                {"/run/gate": volumes["socket"]} if i else
                {"/run/gate": volumes["socket"], "/run/secrets": volumes["secret"], "/state": volumes["state"]})
        assert docker("start", names[0]).returncode == 0
        ready = False
        for _ in range(40):
            logs = docker("logs", names[0])
            if '"credential_loaded": true' in logs.stdout:
                ready = True
                break
            time.sleep(0.25)
        assert ready, "positive_control_broker_not_ready"
        report["broker_positive_control"] = json.loads(logs.stdout.splitlines()[0])
        executed = docker("start", "--attach", names[1], timeout=60)
        report["isolation_tests_executed"] = True
        report["agent_result"] = json.loads(executed.stdout)
        assert executed.returncode == 0 and report["agent_result"]["all_checks_passed"]
        count = docker("exec", "--user", "1000:1000", names[0], "python", "-c",
                       "import sqlite3; print(sqlite3.connect('/state/provider.db').execute('SELECT COUNT(*) FROM effect').fetchone()[0])")
        assert count.returncode == 0 and count.stdout.strip() == "1"
        report["simulated_effect_count"] = 1
        report["status"] = "passed_bounded_container_isolation"
    except Exception as exc:
        report.update(status="failed_or_incomplete", failure_type=type(exc).__name__)
    finally:
        cleanup = []
        for name in reversed(created_containers):
            cleanup.append({"resource": name, "exit_code": docker("rm", "--force", name).returncode})
        for volume in reversed(created_volumes):
            cleanup.append({"resource": volume, "exit_code": docker("volume", "rm", volume).returncode})
        report["cleanup"] = cleanup
        if any(item["exit_code"] != 0 for item in cleanup):
            report["status"] = "cleanup_incomplete"
        save()
    print(json.dumps({"status": report["status"], "isolation_tests_executed": report["isolation_tests_executed"]}))
    return 0 if report["status"] == "passed_bounded_container_isolation" else 1


if __name__ == "__main__":
    raise SystemExit(main())
