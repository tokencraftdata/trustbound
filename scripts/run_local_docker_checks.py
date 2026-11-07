"""Check the current local Docker connection, then run synthetic isolation probes.

Uses the operator's current Docker context; never switches it, starts/resets
Docker, exposes TCP, reads provider keys, or changes daemon configuration.
Standard-library only, including on macOS Python 3.9.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "results" / ("docker-terminal-" + stamp)
    output.mkdir(parents=True)
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "diagnosing", "isolation_tests_executed": False,
              "real_provider_calls": 0, "commands": []}
    def save():
        (output / "connection-report.json").write_text(json.dumps(report, indent=2) + "\n")
    docker = shutil.which("docker")
    if not docker and Path("/usr/local/bin/docker").is_file():
        docker = "/usr/local/bin/docker"
    if not docker:
        report["status"] = "blocked_cli_missing"
        save()
        print("Docker CLI not found. Evidence: " + str(output))
        return 2
    env = dict(os.environ)
    env["PATH"] = str(Path(docker).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    def query(*args):
        try:
            result = subprocess.run([docker, *args], capture_output=True, text=True,
                                    timeout=20, env=env)
            item = {"args": list(args), "exit_code": result.returncode,
                    "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
        except (OSError, subprocess.TimeoutExpired) as exc:
            item = {"args": list(args), "exit_code": None, "error": type(exc).__name__}
        report["commands"].append(item)
        return item
    context = query("context", "show")
    name = context.get("stdout", "")
    # DOCKER_CONTEXT takes precedence over DOCKER_HOST, as in the Docker CLI.
    if os.environ.get("DOCKER_HOST") and not os.environ.get("DOCKER_CONTEXT"):
        endpoint = os.environ["DOCKER_HOST"]
    elif context["exit_code"] == 0 and name:
        inspected = query("context", "inspect", name, "--format", "{{.Endpoints.docker.Host}}")
        endpoint = inspected.get("stdout", "") if inspected["exit_code"] == 0 else ""
    else:
        endpoint = ""
    if not endpoint.startswith("unix://"):
        report["status"] = "blocked_nonlocal_or_unknown_endpoint"
        save()
        print("No confirmed local Unix-socket endpoint; tests were not run. Evidence: " + str(output))
        return 2
    report["endpoint"] = endpoint
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(3)
    try:
        sock.connect(endpoint[len("unix://"):])
        report["socket_connect"] = {"success": True}
    except OSError as exc:
        report["socket_connect"] = {"success": False, "errno": exc.errno, "error": str(exc)}
    finally:
        sock.close()
    version = query("version")
    print("Docker context: " + name)
    print(version.get("stdout", ""))
    if version.get("stderr"):
        print(version["stderr"])
    if version["exit_code"] != 0:
        report["status"] = "blocked_runtime_unavailable"
        save()
        print("No reachable engine. In Docker Desktop, quit and reopen the app, wait for Engine running, then rerun this command. Do not factory-reset Docker.")
        print("Evidence: " + str(output))
        return 2
    report["status"] = "connection_succeeded_harness_pending"
    save()
    print("Engine reachable. Running isolated broker/agent checks with a synthetic credential and local payment simulator.", flush=True)
    work = root.parent / "work" / "credential-boundary" / stamp
    result = subprocess.run([sys.executable, str(root / "scripts/validate_credential_containers.py"),
                             "--work", str(work), "--output", str(output)], env=env)
    report["harness_exit_code"] = result.returncode
    evidence = output / "container-report.json"
    if evidence.exists():
        container = json.loads(evidence.read_text())
        report["status"] = container["status"]
        report["isolation_tests_executed"] = container["isolation_tests_executed"]
    else:
        report["status"] = "harness_incomplete_without_report"
    save()
    print("Evidence: " + str(output))
    return result.returncode if evidence.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
