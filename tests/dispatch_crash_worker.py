"""Child process killed at selected boundaries; provider is a LOCAL simulator."""
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
from trustbound.stripe_gate import StripeGate


def row(status="requires_payment_method"):
    return {"id": "pi_Crash1", "object": "payment_intent", "livemode": False,
            "amount": 200, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": status,
            "amount_received": 200 if status == "succeeded" else 0, "amount_capturable": 0}


class KillGate(StripeGate):
    active_point = None

    def _transaction(self, operation):
        if self.active_point and self.active_point.endswith("before_commit"):
            self.db.set_trace_callback(lambda sql: kill() if sql == "COMMIT" else None)
        result = super()._transaction(operation)
        if self.active_point and self.active_point.endswith("after_commit"):
            kill()
        return result


def kill():
    os.kill(os.getpid(), signal.SIGKILL)


class LocalProvider:
    def __init__(self, db, point=""):
        self.path, self.point = db, point

    def request(self, method, path, body, idem):
        assert method == "POST" and path == "/v1/payment_intents/pi_Crash1/capture" and body == {}
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA synchronous=EXTRA")
        conn.execute("INSERT INTO effects(path,idem) VALUES (?,?)", (path, idem))
        if self.point == "send_before_provider_commit":
            kill()
        conn.commit()
        if self.point == "send_after_provider_commit":
            kill()
        conn.close()
        return 200, {**row("succeeded"), "client_secret": "DO_NOT_EXPORT"}


def main():
    directory, point = Path(sys.argv[1]), sys.argv[2]
    gate = KillGate(directory / "gate.db", "crash-epoch")
    if point.startswith("register_"):
        gate.active_point = point
        gate.register(row())
    elif point.startswith("grant_"):
        gate.active_point = point
        gate.grant("pi_Crash1", "capture")
    elif point.startswith("fence_"):
        gate.active_point = point
        gate.fence()
    elif point.startswith("conflict_"):
        gate.active_point = point
        gate.observe(row("succeeded"))
    else:
        if point.startswith("claim_"):
            gate.active_point = point
        result = gate.dispatch(1, LocalProvider(directory / "provider.db", point))
        assert "DO_NOT_EXPORT" not in json.dumps(result)
        if point == "after_reply":
            kill()
        if point.startswith("observation_"):
            gate.active_point = point
            gate.observe(row("succeeded"))
    raise RuntimeError("expected_checkpoint_not_reached")


if __name__ == "__main__":
    main()
