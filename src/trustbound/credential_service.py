"""Fixed command-ID interface for an isolated trusted dispatcher.

This is an interface, not process isolation. The caller cannot supply transport,
URLs, provider identities, amounts, receipts or SQL. OS containment must prevent
direct credential/database/code access. Current executable harness uses a local
provider simulator and a synthetic credential, never a Stripe key.
"""
import json
import os
from pathlib import Path
import socket
import sqlite3

from trustbound.stripe_gate import StripeGate

MAX_REQUEST = 4096


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def decode_request(raw):
    if not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("request_size")
    request = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    if type(request) is not dict:
        raise ValueError("object_required")
    if request == {"op": "snapshot"} or request == {"op": "reconcile"}:
        return request
    if (set(request) == {"op", "command_id"} and request["op"] == "dispatch"
            and type(request["command_id"]) is int and 1 <= request["command_id"] <= 2**31 - 1):
        return request
    raise ValueError("unsupported_request")


class CommandService:
    def __init__(self, gate, provider):
        self.gate, self.provider = gate, provider

    def handle(self, raw):
        try:
            request = decode_request(raw)
            if request["op"] == "dispatch":
                result = self.gate.dispatch(request["command_id"], self.provider)
            else:
                if request["op"] == "reconcile":
                    for entry in self.gate.snapshot()["records"]:
                        self.gate.observe(self.provider.retrieve(entry["id"]))
                snapshot = self.gate.snapshot()
                result = {key: snapshot[key] for key in
                          ("closed", "known_manifest_resolved", "retained_minor",
                           "has_contract_conflicts", "deployment_completeness_proved")}
            return {"ok": True, "result": result}
        except Exception:
            # Do not serialize provider exception bodies or any raw response.
            return {"ok": False, "error": "request_rejected_or_unresolved"}


def intent(status="requires_payment_method"):
    return {"id": "pi_Boundary1", "object": "payment_intent", "livemode": False,
            "amount": 200, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": status,
            "amount_received": 200 if status == "succeeded" else 0,
            "amount_capturable": 200 if status == "requires_capture" else 0}


class SyntheticProvider:
    def __init__(self, path, credential):
        self.credential = credential
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS effect(id INTEGER PRIMARY KEY, path TEXT)")
        self.db.commit()

    def request(self, method, path, body, idem):
        if method != "POST" or path != "/v1/payment_intents/pi_Boundary1/capture" or body != {}:
            raise ValueError("scope")
        self.db.execute("INSERT INTO effect(path) VALUES (?)", (path,))
        self.db.commit()  # Deliberately no deduplication to reveal double sends.
        return 200, {**intent("succeeded"), "client_secret": self.credential}

    def retrieve(self, payment_id):
        if payment_id != "pi_Boundary1":
            raise ValueError("scope")
        count = self.db.execute("SELECT COUNT(*) FROM effect").fetchone()[0]
        return intent("succeeded" if count else "requires_capture")


def serve(socket_path, state_dir, credential_path):
    credential = Path(credential_path).read_text().strip()
    if not credential.startswith("TB_BOUNDARY_CANARY_"):
        raise ValueError("synthetic_credential_required")
    gate = StripeGate(Path(state_dir) / "gate.db", "boundary-epoch")
    # Only trusted startup provisions a fixed, previously reviewed operation.
    if not gate.snapshot()["records"]:
        gate.register(intent())
        gate.grant("pi_Boundary1", "capture")
        gate.fence()
    provider = SyntheticProvider(Path(state_dir) / "provider.db", credential)
    service = CommandService(gate, provider)
    path = Path(socket_path)
    if path.exists():
        path.unlink()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(str(path))
    os.chmod(path, 0o666)  # Access requires the socket-directory mount capability.
    listener.listen(8)
    print(json.dumps({"ready": True, "credential_loaded": True, "mode": "synthetic_provider",
                      "uid": os.geteuid()}), flush=True)
    while True:
        connection, _ = listener.accept()
        with connection:
            connection.settimeout(2)
            try:
                raw = connection.makefile("rb").readline(MAX_REQUEST + 1)
                reply = service.handle(raw)
                connection.sendall(json.dumps(reply).encode() + b"\n")
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--credential", required=True)
    args = parser.parse_args()
    serve(args.socket, args.state, args.credential)
