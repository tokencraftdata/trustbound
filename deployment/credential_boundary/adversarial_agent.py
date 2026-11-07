"""Run only inside the constrained agent container. No provider credentials."""
import json
import os
from pathlib import Path
import socket


checks = []
def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


def denied(name, operation):
    try:
        operation()
        check(name, False)
    except OSError:
        check(name, True)


def rpc(raw):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(4)
        client.connect("/run/gate/control.sock")
        client.sendall(raw + b"\n")
        return json.loads(client.makefile("rb").readline(8192))


check("agent_uid_2000", os.geteuid() == 2000)
denied("provider_credential_unreadable", lambda: Path("/run/secrets/provider-key").read_bytes())
denied("gate_database_unreadable", lambda: Path("/state/gate.db").read_bytes())
denied("gate_database_not_creatable", lambda: Path("/state/gate.db").write_bytes(b"corrupt"))
denied("service_code_not_writable", lambda: Path("/app/trustbound/credential_service.py").open("ab"))
denied("root_filesystem_not_writable", lambda: Path("/unauthorized").write_bytes(b"x"))
denied("cannot_replace_gate_socket", lambda: Path("/run/gate/control.sock").unlink())
check("docker_socket_not_mounted", not Path("/var/run/docker.sock").exists())
check("host_credential_tree_not_mounted", not Path("/Users").exists())
check("no_provider_key_in_environment", not any("STRIPE" in k or "TB_BOUNDARY_CANARY_" in v for k,v in os.environ.items()))
visible = []
for item in Path("/proc").iterdir():
    if item.name.isdigit():
        try:
            visible.append((item / "cmdline").read_bytes())
        except OSError:
            pass
check("broker_process_not_visible", not any(b"-m\x00trustbound.credential_service" in cmd for cmd in visible))
def direct_network():
    with socket.create_connection(("1.1.1.1", 443), timeout=2):
        pass
denied("no_direct_external_connection", direct_network)

initial = rpc(b'{"op":"snapshot"}')
check("positive_control_socket_service_available", initial.get("ok") is True and initial["result"]["closed"])
bad = [b'{"op":"read","path":"/run/secrets/provider-key"}',
       b'{"op":"create","confirm":true}', b'{"op":"grant","payment_id":"pi_Outside"}',
       b'{"op":"observe","status":"canceled"}', b'{"op":"fence","closed":false}',
       b'{"op":"dispatch","command_id":1,"path":"/v1/payment_intents"}',
       b'{"op":"dispatch","command_id":1,"amount":999999}',
       b'{"op":"dispatch","command_id":1,"transport":"attacker"}',
       b'{"op":"dispatch","command_id":true}', b'{"op":"dispatch","command_id":999}',
       b'{"op":"snapshot","op":"dispatch","command_id":1}', b'__import__("os")',
       b' ' * 4097]
for i, request in enumerate(bad):
    reply = rpc(request)
    check("unauthorized_request_" + str(i), reply == {"ok": False, "error": "request_rejected_or_unresolved"})
first = rpc(b'{"op":"dispatch","command_id":1}')
check("positive_control_authorized_command_executes", first.get("ok") is True and first["result"]["http_status"] == 200)
check("raw_provider_secret_not_returned", "TB_BOUNDARY_CANARY_" not in json.dumps(first))
check("repeat_command_rejected", rpc(b'{"op":"dispatch","command_id":1}')["ok"] is False)
check("post_reply_still_needs_reconciliation", rpc(b'{"op":"snapshot"}')["result"]["known_manifest_resolved"] is False)
final = rpc(b'{"op":"reconcile"}')["result"]
check("authoritative_simulated_reconciliation", final["known_manifest_resolved"] and final["retained_minor"] == 200)
check("no_complete_deployment_claim", final["deployment_completeness_proved"] is False)
print(json.dumps({"checks": checks, "all_checks_passed": all(c["passed"] for c in checks),
                  "provider": "local_simulator", "real_provider_calls": 0}))
raise SystemExit(0 if all(c["passed"] for c in checks) else 1)
