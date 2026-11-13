"""Fixed command-ID interface for an isolated trusted dispatcher.

This is an interface, not process isolation. The caller cannot supply transport,
URLs, provider identities, amounts, receipts or SQL. OS containment must prevent
direct credential/database/code access. Current executable harness uses a local
provider simulator and a synthetic credential, never a Stripe key.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path
from typing import Any, NoReturn, Protocol

from trustbound.stripe_gate import PaymentObservation, PaymentTransport, StripeGate

MAX_REQUEST = 4096
MAX_COMMAND_ID = 2**31 - 1
_PUBLIC_SNAPSHOT_FIELDS = (
    "closed",
    "known_manifest_resolved",
    "retained_minor",
    "has_contract_conflicts",
    "deployment_completeness_proved",
)


class PaymentProvider(PaymentTransport, Protocol):
    """Trusted dispatch transport with authoritative retrieval for reconciliation."""

    def retrieve(self, payment_id: str) -> PaymentObservation: ...


def unique_object(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of silently accepting the last value."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _reject_nonfinite(_value: str) -> NoReturn:
    raise ValueError("nonfinite")


def decode_request(raw: bytes) -> dict[str, Any]:
    """Accept only the three supported operations with their exact field sets."""
    if not 0 < len(raw) <= MAX_REQUEST:
        raise ValueError("request_size")
    request = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=_reject_nonfinite,
    )
    if type(request) is not dict:
        raise ValueError("object_required")
    if request == {"op": "snapshot"} or request == {"op": "reconcile"}:
        return request
    if (
        set(request) == {"op", "command_id"}
        and request["op"] == "dispatch"
        and type(request["command_id"]) is int
        and 1 <= request["command_id"] <= MAX_COMMAND_ID
    ):
        return request
    raise ValueError("unsupported_request")


class CommandService:
    def __init__(self, gate: StripeGate, provider: PaymentProvider) -> None:
        self.gate = gate
        self.provider = provider

    def _reconcile(self) -> None:
        for entry in self.gate.snapshot()["records"]:
            self.gate.reconcile(entry["id"], self.provider.retrieve)

    def _public_snapshot(self) -> dict[str, Any]:
        snapshot = self.gate.snapshot()
        return {key: snapshot[key] for key in _PUBLIC_SNAPSHOT_FIELDS}

    def handle(self, raw: bytes) -> dict[str, Any]:
        try:
            request = decode_request(raw)
            if request["op"] == "dispatch":
                result = self.gate.dispatch(request["command_id"], self.provider)
            else:
                if request["op"] == "reconcile":
                    self._reconcile()
                result = self._public_snapshot()
            return {"ok": True, "result": result}
        except Exception:
            # Do not serialize provider exception bodies or any raw response.
            return {"ok": False, "error": "request_rejected_or_unresolved"}


def intent(status: str = "requires_payment_method") -> dict[str, Any]:
    """Build the fixed synthetic intent used by the local boundary harness."""
    return {
        "id": "pi_Boundary1",
        "object": "payment_intent",
        "livemode": False,
        "amount": 200,
        "currency": "usd",
        "confirmation_method": "manual",
        "capture_method": "manual",
        "payment_method_types": ["card"],
        "payment_method": None,
        "customer": None,
        "status": status,
        "amount_received": 200 if status == "succeeded" else 0,
        "amount_capturable": 200 if status == "requires_capture" else 0,
    }


class SyntheticProvider:
    def __init__(self, path: str | Path, credential: str) -> None:
        self.credential = credential
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS effect(id INTEGER PRIMARY KEY, path TEXT)"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def request(
        self, method: str, path: str, body: dict[str, str], idem: str
    ) -> tuple[int, dict[str, Any]]:
        if (
            method != "POST"
            or path != "/v1/payment_intents/pi_Boundary1/capture"
            or body != {}
        ):
            raise ValueError("scope")
        self.db.execute("INSERT INTO effect(path) VALUES (?)", (path,))
        self.db.commit()  # Deliberately no deduplication to reveal double sends.
        return 200, {**intent("succeeded"), "client_secret": self.credential}

    def retrieve(self, payment_id: str) -> dict[str, Any]:
        if payment_id != "pi_Boundary1":
            raise ValueError("scope")
        count = self.db.execute("SELECT COUNT(*) FROM effect").fetchone()[0]
        return intent("succeeded" if count else "requires_capture")


def _serve_requests(path: Path, service: CommandService) -> None:
    if path.exists():
        path.unlink()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        os.chmod(path, 0o666)  # Access requires the socket-directory mount capability.
        listener.listen(8)
        print(
            json.dumps(
                {
                    "ready": True,
                    "credential_loaded": True,
                    "mode": "synthetic_provider",
                    "uid": os.geteuid(),
                }
            ),
            flush=True,
        )
        while True:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(2)
                try:
                    with connection.makefile("rb") as request_stream:
                        raw = request_stream.readline(MAX_REQUEST + 1)
                    reply = service.handle(raw)
                    connection.sendall(json.dumps(reply).encode() + b"\n")
                except (OSError, ValueError):
                    pass


def serve(
    socket_path: str | Path, state_dir: str | Path, credential_path: str | Path
) -> None:
    credential = Path(credential_path).read_text().strip()
    if not credential.startswith("TB_BOUNDARY_CANARY_"):
        raise ValueError("synthetic_credential_required")
    state = Path(state_dir)
    with closing(StripeGate(state / "gate.db", "boundary-epoch")) as gate:
        # Only trusted startup provisions a fixed, previously reviewed operation.
        if not gate.snapshot()["records"]:
            gate.register(intent())
            gate.grant("pi_Boundary1", "capture")
            gate.fence()
        with closing(SyntheticProvider(state / "provider.db", credential)) as provider:
            _serve_requests(Path(socket_path), CommandService(gate, provider))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--credential", required=True)
    args = parser.parse_args()
    serve(args.socket, args.state, args.credential)


if __name__ == "__main__":
    main()
