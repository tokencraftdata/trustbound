"""Small, one-shot real Stripe SANDBOX probe, never a production adapter.

Fixed synthetic amounts/test methods only. No automatic HTTP retries. Uses
separate local flight/hotel databases and a LOCAL admission log, not a Stripe
epoch fence. Missing responses remain unresolved. Booking providers are absent.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
import uuid

from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor
from trustbound.sandbox_observer import StripeSandboxObserver, STRIPE_VERSION, _NoRedirect


def safe_payment(data):
    return {field: data.get(field) for field in (
        "id", "object", "livemode", "amount", "currency", "amount_received",
        "amount_capturable", "status", "created",
    )}


class ProbeClient:
    def __init__(self, key, run_dir, run_id):
        StripeSandboxObserver(key)  # Strict test-only credential validation.
        self.key, self.run_id = key, run_id
        self.started = time.monotonic()
        self.calls = []
        self.db = sqlite3.connect(run_dir / "request-journal.db")
        self.db.execute("CREATE TABLE request(n INTEGER PRIMARY KEY, method TEXT, path TEXT, idem TEXT, body TEXT, state TEXT)")
        self.db.commit()

    def request(self, method, path, body=None, idem=None):
        if time.monotonic() - self.started > 600 or len(self.calls) >= 40:
            raise RuntimeError("probe_limit_reached_no_automatic_retry")
        if method == "GET":
            if not re.fullmatch(r"/v1/payment_intents(?:\?limit=100|/pi_[A-Za-z0-9]+)", path):
                raise ValueError("unsupported_read")
        elif method == "POST":
            if not idem or not idem.startswith(self.run_id + ":"):
                raise ValueError("run_bound_idempotency_required")
            if not re.fullmatch(r"/v1/payment_intents(?:/pi_[A-Za-z0-9]+/(?:confirm|capture|cancel))?", path):
                raise ValueError("unsupported_write")
            if path == "/v1/payment_intents":
                if type(body.get("amount")) is not int or not 50 <= body["amount"] <= 1000:
                    raise ValueError("probe_amount_limit")
                if body.get("currency") != "usd" or body.get("capture_method") != "manual":
                    raise ValueError("probe_scope_required")
            if body and "payment_method" in body and body["payment_method"] not in {"pm_card_visa", "pm_card_chargeDeclined"}:
                raise ValueError("synthetic_payment_method_required")
        else:
            raise ValueError("unsupported_method")
        n = self.db.execute("SELECT COUNT(*) FROM request").fetchone()[0] + 1
        self.db.execute("INSERT INTO request VALUES (?, ?, ?, ?, ?, 'dispatched_unknown')",
                        (n, method, path, idem, json.dumps(body)))
        self.db.commit()  # Write ahead of every possible provider effect.
        headers = {"Authorization": "Bearer " + self.key, "Stripe-Version": STRIPE_VERSION}
        if idem:
            headers["Idempotency-Key"] = idem
        payload = None if method == "GET" else urlencode(body or {}).encode()
        req = Request("https://api.stripe.com" + path, headers=headers, data=payload, method=method)
        try:
            try:
                response = build_opener(_NoRedirect()).open(req, timeout=15)
            except HTTPError as exc:
                response = exc
            with response:
                code = response.code
                request_id = response.headers.get("Request-Id")
                raw = response.read(1_048_577)
                if len(raw) > 1_048_576:
                    raise RuntimeError("response_too_large")
                data = json.loads(raw)
        except (TimeoutError, URLError, OSError, ValueError):
            self.calls.append({"method": method, "path": path, "outcome": "unknown"})
            raise RuntimeError("response_unknown_stop_and_reconcile") from None
        if code < 300:
            objects = data.get("data", []) if data.get("object") == "list" else [data]
            if any(row.get("livemode") is not False for row in objects):
                raise RuntimeError("non_sandbox_response_rejected")
        error = data.get("error", {})
        entry = {"method": method, "path": path, "http_status": code,
                 "request_id": request_id, "observed_at": datetime.now(timezone.utc).isoformat()}
        if error:
            entry["error"] = {k: error.get(k) for k in ("type", "code", "decline_code")}
        elif data.get("object") == "list":
            entry.update({"records": [safe_payment(row) for row in data["data"]], "has_more": data["has_more"]})
        else:
            entry["payment"] = safe_payment(data)
        self.calls.append(entry)
        self.db.execute("UPDATE request SET state = 'response_received' WHERE n = ?", (n,))
        self.db.commit()
        return code, data


def run(key, root):
    # Refuse existing directories: reruns must not blindly replay unknown writes.
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    run_id = "tb-" + uuid.uuid4().hex
    api = ProbeClient(key, root, run_id)
    observer = StripeSandboxObserver(key)
    processor = FencedProcessor("local-admission-not-stripe", root / "processor.db")
    processor.open_epoch(run_id)
    flight = PersistentCoordinator("flight", 600, root / "flight.db")
    hotel = PersistentCoordinator("hotel", 400, root / "hotel.db")
    report = {"run_id": run_id, "environment": "real_stripe_sandbox_api",
              "api_version": STRIPE_VERSION, "checks": [], "calls": api.calls,
              "booking_api_executed": False, "epoch_completeness_established": False,
              "independent_issuer_observers": False, "all_checks_passed": False}
    def check(name, condition, evidence=None):
        report["checks"].append({"name": name, "passed": bool(condition), "evidence": evidence})
        if not condition:
            raise RuntimeError("check_failed:" + name)
    def create(amount, label, confirm=True, method="pm_card_visa"):
        return {"amount": amount, "currency": "usd", "capture_method": "manual",
                "allowed_payment_method_types[]": "card", "payment_method": method,
                "confirm": "true" if confirm else "false", "metadata[trustbound_run]": run_id,
                "metadata[scenario]": label}
    try:
        for coord, leg, amount in ((flight, "flight", 600), (hotel, "hotel", 400)):
            coord.reserve_quote(leg, 1, amount)
            coord.submit(processor, run_id, leg, 1, run_id + ":" + leg)
        flight_body = create(600, "flight")
        code, f = api.request("POST", "/v1/payment_intents", flight_body, run_id + ":flight-create")
        check("flight_authorized", code == 200 and f.get("status") == "requires_capture")
        code, replay = api.request("POST", "/v1/payment_intents", flight_body, run_id + ":flight-create")
        check("duplicate_create_same_object", code == 200 and replay.get("id") == f["id"])
        code, changed = api.request("POST", "/v1/payment_intents", {**flight_body, "amount": 650}, run_id + ":flight-create")
        check("changed_payload_same_key_rejected", code == 400 and changed.get("error", {}).get("type") == "idempotency_error")
        try:
            flight.reserve_quote("flight", 2, 650)
            blocked = False
        except RuntimeError as exc:
            blocked = str(exc) == "allocation_exceeded"
        check("local_quote_revision_retains_old_exposure", blocked and flight.snapshot()["liability_minor"] == 600)
        hotel_body = create(400, "hotel")
        code, h_original = api.request("POST", "/v1/payment_intents", hotel_body, run_id + ":hotel-create")
        check("hotel_provider_accepted_before_injected_loss", code == 200 and h_original.get("status") == "requires_capture")
        # Discard response at application boundary and restart local coordinator.
        # Audit trace retains the response for the experiment grader only.
        hotel.close()
        hotel = PersistentCoordinator("hotel", 400, root / "hotel.db")
        check("injected_lost_response_retains_liability_after_restart", hotel.snapshot()["liability_minor"] == 400,
              "client-side response discard; not a provider timeout")
        hotel.submit(processor, run_id, "hotel", 1, run_id + ":hotel")
        code, h = api.request("POST", "/v1/payment_intents", hotel_body, run_id + ":hotel-create")
        check("retry_after_injected_loss_same_object", code == 200 and h.get("id") == h_original["id"])
        code, captured = api.request("POST", f"/v1/payment_intents/{f['id']}/capture", {}, run_id + ":flight-capture")
        check("flight_capture_succeeded", code == 200 and captured.get("amount_received") == 600)
        # Fresh GET, rather than the POST reply, supplies the applied observation.
        fo = observer.retrieve(f["id"])
        check("fresh_get_confirms_flight", fo["status"] == "confirmed" and fo["amount_minor"] == 600)
        flight.apply_receipt(run_id + ":flight", fo["status"])
        check("partial_outcome_retains_both_liabilities", flight.snapshot()["liability_minor"] + hotel.snapshot()["liability_minor"] == 1000)
        code, canceled = api.request("POST", f"/v1/payment_intents/{h['id']}/cancel", {}, run_id + ":hotel-cancel")
        check("hotel_cancellation_succeeded", code == 200 and canceled.get("status") == "canceled")
        code, rejected = api.request("POST", f"/v1/payment_intents/{h['id']}/capture", {}, run_id + ":hotel-late-capture")
        check("capture_after_cancellation_rejected", code == 400 and rejected.get("error", {}).get("code") == "payment_intent_unexpected_state")
        ho = observer.retrieve(h["id"])
        check("fresh_get_confirms_hotel_zero_release", ho["status"] == "released" and ho["received_minor"] == 0)
        hotel.apply_receipt(run_id + ":hotel", ho["status"])
        report["fresh_observations"] = [fo, ho]
        report["local_snapshots"] = [flight.snapshot(), hotel.snapshot()]
        # Additional explicitly out-of-trip test objects exercise failure/detection.
        code, decline = api.request("POST", "/v1/payment_intents", create(200, "decline", False, "pm_card_chargeDeclined"), run_id + ":decline-create")
        check("decline_probe_created", code == 200 and decline.get("id", "").startswith("pi_"))
        code, declined = api.request("POST", f"/v1/payment_intents/{decline['id']}/confirm", {}, run_id + ":decline-confirm")
        check("actual_provider_decline", code == 402 and declined.get("error", {}).get("code") == "card_declined")
        do = observer.retrieve(decline["id"])
        check("decline_not_misclassified_terminal_release", do["status"] == "uncertain")
        code, _ = api.request("POST", f"/v1/payment_intents/{decline['id']}/cancel", {}, run_id + ":decline-cancel")
        check("decline_probe_canceled", code == 200)
        # Known-object retrieval misses this object absent from the trip manifest.
        code, extra = api.request("POST", "/v1/payment_intents", create(100, "out-of-manifest", False), run_id + ":extra-create")
        check("out_of_manifest_probe_created", code == 200)
        code, population = api.request("GET", "/v1/payment_intents?limit=100")
        check("list_query_completed_single_page", code == 200 and population.get("has_more") is False)
        rows = {row["id"]: row for row in population["data"]}
        check("separate_list_matches_known_payment_outcomes",
              all(rows[o["payment_id"]]["status"] == o["provider_status"] and
                  rows[o["payment_id"]]["amount"] == o["amount_minor"] and
                  rows[o["payment_id"]]["amount_received"] == o["received_minor"] and
                  rows[o["payment_id"]]["currency"] == o["currency"] for o in [fo, ho]))
        unexpected = sorted(set(rows) - {f["id"], h["id"]})
        check("list_detects_objects_missing_from_trip_manifest", extra["id"] in unexpected and decline["id"] in unexpected,
              {"unexpected_ids": unexpected, "same_processor_not_independent_issuer": True})
        code, _ = api.request("POST", f"/v1/payment_intents/{extra['id']}/cancel", {}, run_id + ":extra-cancel")
        check("out_of_manifest_probe_canceled", code == 200)
        report["all_checks_passed"] = True
    except Exception as exc:
        # Never emit exception bodies containing provider response material.
        report["stopped"] = {"exception_type": type(exc).__name__}
        raise
    finally:
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        (root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        flight.close()
        hotel.close()
        processor.close()
        api.db.close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--execute-sandbox", action="store_true", required=True)
    args = parser.parse_args()
    key = os.environ.get("TRUSTBOUND_STRIPE_TEST_KEY", "")
    StripeSandboxObserver(key)
    try:
        report = run(key, args.run_dir)
    except Exception as exc:
        print(json.dumps({"completed": False, "exception_type": type(exc).__name__,
                          "instruction": "Inspect sanitized report; do not blindly retry"}))
        return 1
    print(json.dumps({"completed": True, "checks_passed": len(report["checks"]),
                      "api_calls_in_trace": len(report["calls"]),
                      "booking_api_executed": False, "epoch_completeness_established": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
