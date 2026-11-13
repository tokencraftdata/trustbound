"""Shared experiment plumbing; scenario oracles remain in their own evaluators."""
from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import sqlite3
from typing import Any

PAYMENT = "pi_Schedule1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class SinglePaymentProvider:
    """Separate durable simulator: cancellation and success are irreversible."""

    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS state(status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS calls(action TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS effects(identity TEXT NOT NULL);
        """)
        if not self.db.execute("SELECT 1 FROM state").fetchone():
            with self.db:
                self.db.execute("INSERT INTO state VALUES ('requires_payment_method')")
        self.lose_reply = False

    @property
    def status(self):
        return self.db.execute("SELECT status FROM state").fetchone()[0]

    def observation(self):
        return {
            "id": PAYMENT, "object": "payment_intent", "livemode": False,
            "amount": 200, "currency": "usd", "confirmation_method": "manual",
            "capture_method": "manual", "payment_method_types": ["card"],
            "payment_method": None, "customer": None, "status": self.status,
            "amount_received": 200 if self.status == "succeeded" else 0,
            "amount_capturable": 200 if self.status == "requires_capture" else 0,
        }

    def request(self, method, path, body, idem):
        action = path.rsplit("/", 1)[-1]
        require(method == "POST" and path == f"/v1/payment_intents/{PAYMENT}/{action}", "wrong dispatch target")
        require(action in {"confirm", "capture"}, "unsupported dispatch")
        require(body == ({"payment_method": "pm_card_visa"} if action == "confirm" else {}), "wrong dispatch body")
        require(idem == f"schedule-epoch:dispatch:{1 if action == 'confirm' else 2}", "wrong command identity")
        paid = False
        with self.db:
            self.db.execute("INSERT INTO calls VALUES (?)", (action,))
            if action == "confirm" and self.status == "requires_payment_method":
                self.db.execute("UPDATE state SET status='requires_capture'")
            elif action == "capture" and self.status == "requires_capture":
                self.db.execute("UPDATE state SET status='succeeded'")
                self.db.execute("INSERT INTO effects VALUES (?)", (PAYMENT,))
                paid = True
            else:
                return 400, {}
        if paid and self.lose_reply:
            raise TimeoutError("injected lost reply after provider commit")
        return 200, self.observation()

    def cancel(self):
        with self.db:
            if self.status == "requires_capture":
                self.db.execute("UPDATE state SET status='canceled'")


def write_report(path: Path, run: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Reserve a new output and preserve a failed run's diagnostic prefix."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as output:
        try:
            report = run()
        except Exception as exc:
            json.dump({"checks_passed": False, "error": str(exc)}, output, indent=2)
            output.write("\n")
            raise
        json.dump(report, output, indent=2)
        output.write("\n")
    return report
