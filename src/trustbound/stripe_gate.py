"""Narrow durable dispatch gate for one Stripe test epoch; not a verified deployment.

The transport/credential boundary must enforce this gate. A process holding the
same Stripe key can bypass it. SQLite durability assumes honest stable storage.
"""
import re
import sqlite3


class StripeGate:
    def __init__(self, path, epoch):
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=EXTRA")
        self.db.execute("PRAGMA fullfsync=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS epoch(id TEXT PRIMARY KEY, closed INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS payment(id TEXT PRIMARY KEY, amount INTEGER NOT NULL,
          status TEXT NOT NULL, received INTEGER NOT NULL, capturable INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS command(id INTEGER PRIMARY KEY, payment_id TEXT NOT NULL,
          action TEXT NOT NULL, claimed INTEGER NOT NULL DEFAULT 0,
          UNIQUE(payment_id, action));
        """)
        def initialize():
            rows = self.db.execute("SELECT id FROM epoch").fetchall()
            if rows and rows != [(epoch,)]:
                raise ValueError("epoch_identity_mismatch")
            self.db.execute("INSERT OR IGNORE INTO epoch VALUES (?, 0)", (epoch,))
        try:
            self._transaction(initialize)
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def _transaction(self, operation):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            result = operation()
            self.db.execute("COMMIT")
            return result
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _open(self):
        if self.db.execute("SELECT closed FROM epoch").fetchone()[0]:
            raise RuntimeError("epoch_fenced")

    def register(self, row):
        # Whitelist configuration: no permissive default on absent evidence.
        if (row.get("object") != "payment_intent" or row.get("livemode") is not False
                or not re.fullmatch(r"pi_[A-Za-z0-9]+", row.get("id", ""))
                or row.get("confirmation_method") != "manual"
                or row.get("capture_method") != "manual"
                or row.get("payment_method_types") != ["card"]
                or row.get("status") != "requires_payment_method"
                or row.get("payment_method") is not None or row.get("customer") is not None
                or row.get("currency") != "usd" or type(row.get("amount")) is not int
                or not 50 <= row["amount"] <= 500
                or row.get("amount_received") != 0 or row.get("amount_capturable") != 0):
            raise ValueError("not_inert_constrained_intent")
        def operation():
            self._open()
            self.db.execute("INSERT INTO payment VALUES (?, ?, 'uncertain', 0, 0)",
                            (row["id"], row["amount"]))
        self._transaction(operation)

    def grant(self, payment_id, action):
        if action not in {"confirm", "capture"}:
            raise ValueError("unsupported_action")
        def operation():
            self._open()
            row = self.db.execute("SELECT status FROM payment WHERE id=?", (payment_id,)).fetchone()
            if row != ("uncertain",):
                raise RuntimeError("unknown_or_terminal_payment")
            cur = self.db.execute("INSERT INTO command(payment_id,action) VALUES (?, ?)",
                                  (payment_id, action))
            return cur.lastrowid
        return self._transaction(operation)

    def claim(self, command_id):
        # An already granted request may execute after the fence. Crash after
        # claim is uncertain; no automatic redispatch. Resolve the known object.
        def operation():
            row = self.db.execute("SELECT payment_id,action,claimed FROM command WHERE id=?",
                                  (command_id,)).fetchone()
            if row is None or row[2]:
                raise RuntimeError("command_unknown_or_already_claimed")
            self.db.execute("UPDATE command SET claimed=1 WHERE id=?", (command_id,))
            return row[:2]
        return self._transaction(operation)

    def fence(self):
        self._transaction(lambda: self.db.execute("UPDATE epoch SET closed=1"))

    def dispatch(self, command_id, transport):
        """Trusted-worker entry point: one claim, one fixed transport invocation.

        `transport` is trusted and must not retry or expose credentials to agents.
        A timeout/exception/worker death leaves the committed claim in place.
        This is an invocation guarantee, not exactly-once provider execution.
        Python object privacy and this method are not process isolation.
        """
        payment_id, action = self.claim(command_id)
        epoch = self.db.execute("SELECT id FROM epoch").fetchone()[0]
        # This adapter is deliberately limited to synthetic Stripe test methods.
        body = {"payment_method": "pm_card_visa"} if action == "confirm" else {}
        code, _ = transport.request("POST", "/v1/payment_intents/" + payment_id + "/" + action,
                                    body, epoch + ":dispatch:" + str(command_id))
        # Do not trust a POST reply as a closure observation or expose raw secrets.
        return {"payment_id": payment_id, "action": action, "http_status": code,
                "requires_authoritative_reconciliation": True}

    def observe(self, row):
        # Caller supplies a fresh authenticated retrieval. This function does
        # not prove that retrieval occurred or that the provider is truthful.
        def operation():
            prior = self.db.execute("SELECT amount,status,received,capturable FROM payment WHERE id=?",
                                    (row.get("id"),)).fetchone()
            if prior is None:
                raise ValueError("unknown_payment")
            if (row.get("object") != "payment_intent" or row.get("livemode") is not False
                    or row.get("currency") != "usd" or row.get("amount") != prior[0]
                    or row.get("confirmation_method") != "manual"
                    or row.get("capture_method") != "manual"
                    or row.get("payment_method_types") != ["card"]
                    or type(row.get("amount_received")) is not int
                    or type(row.get("amount_capturable")) is not int
                    or not 0 <= row["amount_received"] <= prior[0]
                    or not 0 <= row["amount_capturable"] <= prior[0]):
                raise ValueError("observation_scope_mismatch")
            status = "uncertain"
            if row.get("status") == "canceled" and row["amount_capturable"] == 0 and row["amount_received"] == 0:
                status = "canceled"
            if row.get("status") == "succeeded" and row["amount_capturable"] == 0 and row["amount_received"] == prior[0]:
                status = "succeeded"
            state = (status, row["amount_received"], row["amount_capturable"])
            if prior[1] != "uncertain" and state != prior[1:]:
                raise RuntimeError("terminal_observation_changed")
            self.db.execute("UPDATE payment SET status=?,received=?,capturable=? WHERE id=?",
                            (*state, row["id"]))
        self._transaction(operation)

    def snapshot(self):
        def operation():
            closed = bool(self.db.execute("SELECT closed FROM epoch").fetchone()[0])
            rows = [dict(zip(("id", "amount", "status", "received", "capturable"), row))
                    for row in self.db.execute("SELECT * FROM payment ORDER BY id")]
            resolved = all(row["status"] in {"canceled", "succeeded"} for row in rows)
            return {"closed": closed, "records": rows,
                    "known_manifest_resolved": closed and resolved,
                    "deployment_completeness_proved": False,
                    "retained_minor": sum(row["received"] if row["status"] != "uncertain"
                                          else row["amount"] for row in rows)}
        return self._transaction(operation)
