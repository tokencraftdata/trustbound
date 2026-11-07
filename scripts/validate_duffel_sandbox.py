"""Operator-driven Duffel REST test probe; no production keys or blind retries.

Set TRUSTBOUND_DUFFEL_RUN_DIR and TRUSTBOUND_DUFFEL_KEY_FILE. Private records
stay in the run directory; only explicit projections should be published.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid

from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor


CAP_MINOR = 100000


def validate_key(key):
    if not re.fullmatch(r"duffel_test_[A-Za-z0-9_-]+", key):
        raise ValueError("test_token_required")
    return key


def identifier(value, prefix):
    if not isinstance(value, str) or not re.fullmatch(prefix + r"_[A-Za-z0-9]+", value):
        raise ValueError("invalid_resource_identity")
    return value


def minor(value):
    amount = Decimal(str(value)) * 100
    if not amount.is_finite() or amount != amount.to_integral_value() or not 0 < amount <= CAP_MINOR:
        raise ValueError("quote_outside_synthetic_cap")
    return int(amount)


def validate_offer(offer):
    if offer.get("live_mode") is not False:
        raise ValueError("test_mode_required")
    if offer.get("owner", {}).get("name") != "Duffel Airways" or offer["owner"].get("iata_code") != "ZZ":
        raise ValueError("synthetic_airline_required")
    if offer.get("total_currency") != "USD":
        raise ValueError("usd_required")
    identifier(offer.get("id"), "off")
    expiry = datetime.fromisoformat(offer["expires_at"].replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("expired_offer")
    return minor(offer["total_amount"])


def projection(data):
    keys = ("id", "live_mode", "order_id", "status", "type", "total_amount",
            "total_currency", "amount", "currency", "cancelled_at", "confirmed_at",
            "refund_amount", "refund_currency", "refund_to", "created_at", "synced_at",
            "expires_at", "available_actions", "payment_status", "metadata")
    result = {k: data[k] for k in keys if k in data}
    if isinstance(data.get("owner"), dict):
        result["owner"] = {k: data["owner"].get(k) for k in ("id", "name", "iata_code")}
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("redirect_rejected")


class InjectedReplyLoss(OSError):
    """Client-side discard after transport reads; not a measured network timeout."""


class Probe:
    def __init__(self, root, key, discard_book_reply=False):
        self.root = Path(root)
        self.private = self.root / "private"
        self.private.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.key = validate_key(key)
        self.discard_book_reply = discard_book_reply
        self.state_path = self.private / "state.json"
        if not self.state_path.exists():
            with self.state_path.open("x") as f:
                json.dump({"reference": "trustbound-" + uuid.uuid4().hex}, f)
        self.state = json.loads(self.state_path.read_text())

    def save(self):
        self.state_path.write_text(json.dumps(self.state))

    def previous(self, stage):
        result = json.loads((self.root / (stage + "-result.json")).read_text())
        if result.get("http_status") not in (200, 201):
            raise ValueError("prior_stage_not_successful")
        return json.loads((self.private / (stage + "-response.json")).read_text())["data"]

    def request(self, stage, method, path, data=None, timeout=30):
        if not path.startswith("/air/") or ".." in path:
            raise ValueError("invalid_path")
        with (self.private / (stage + "-request.json")).open("x") as f:
            json.dump({"method": method, "path": path, "data": data,
                       "outcome": "unknown", "attempted_at": datetime.now(timezone.utc).isoformat()}, f)
            f.flush()
            os.fsync(f.fileno())
        result = {"stage": stage, "method": method, "path": path,
                  "api_version": "v2", "epoch_completeness_established": False}
        req = Request("https://api.duffel.com" + path, method=method,
                      data=None if data is None else json.dumps({"data": data}).encode(),
                      headers={"Authorization": "Bearer " + self.key, "Duffel-Version": "v2",
                               "Accept": "application/json", "Content-Type": "application/json"})
        try:
            try:
                response = build_opener(NoRedirect()).open(req, timeout=timeout)
            except HTTPError as exc:
                response = exc
            with response:
                raw = response.read(5_000_001)
                if len(raw) > 5_000_000:
                    raise RuntimeError("response_too_large")
                if stage == "book" and self.discard_book_reply:
                    result["fault_injection"] = "client_discard_after_response_read_before_parse"
                    result["response_bytes_discarded"] = True
                    raise InjectedReplyLoss()
                body = json.loads(raw)
                result.update(http_status=response.code, request_id=response.headers.get("x-request-id"),
                              observed_at=datetime.now(timezone.utc).isoformat())
            (self.private / (stage + "-response.json")).write_text(json.dumps(body))
            payload = body.get("data")
            if isinstance(payload, dict):
                result["record"] = projection(payload)
                if isinstance(payload.get("offers"), list):
                    result["offer_count"] = len(payload["offers"])
            elif isinstance(payload, list):
                result["records"] = [projection(x) for x in payload]
                meta = body.get("meta")
                result["has_more"] = (bool(meta["after"]) if isinstance(meta, dict)
                    and "after" in meta and (meta["after"] is None or isinstance(meta["after"], str)) else None)
            if body.get("errors"):
                result["error_codes"] = [{k: e.get(k) for k in ("type", "code")} for e in body["errors"]]
            (self.root / (stage + "-result.json")).write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            if result["http_status"] not in (200, 201):
                raise SystemExit("provider_non_success_do_not_blindly_retry")
            return payload
        except (OSError, ValueError, RuntimeError) as exc:
            result.update(outcome="unknown", retry_performed=False, exception_type=type(exc).__name__)
            (self.root / (stage + "-result.json")).write_text(json.dumps(result, indent=2) + "\n")
            raise SystemExit("outcome_unknown_inspect_and_reconcile") from None

    def own_order(self):
        if (self.private / "recovered-order.json").exists():
            order = json.loads((self.private / "recovered-order.json").read_text())
        else:
            order = self.previous("book")
        if order.get("live_mode") is not False or order.get("metadata", {}).get("trustbound_reference") != self.state["reference"]:
            raise ValueError("own_test_order_binding_required")
        return identifier(order["id"], "ord")

    def run(self, stage):
        if stage == "search":
            return self.request(stage, "POST", "/air/offer_requests?return_offers=true&supplier_timeout=10000", {
                "slices": [{"origin": "SFO", "destination": "JFK", "departure_date": "2026-12-01"}],
                "passengers": [{"type": "adult"}], "cabin_class": "economy"}, timeout=25)
        if stage == "refresh-offer":
            search = self.previous("search")
            if search.get("live_mode") is not False:
                raise ValueError("test_search_required")
            candidates = []
            for offer in search["offers"]:
                try:
                    validate_offer(offer)
                    candidates.append(offer)
                except (ValueError, KeyError):
                    pass
            if not candidates:
                raise ValueError("no_eligible_synthetic_offer")
            selected = min(candidates, key=lambda x: Decimal(x["total_amount"]))
            self.state["selected_offer"] = projection(selected)
            self.save()
            return self.request(stage, "GET", "/air/offers/" + selected["id"])
        if stage == "book":
            if (self.private / "book-request.json").exists():
                raise ValueError("prior_booking_attempt_reconcile_first")
            offer = self.previous("refresh-offer")
            amount = validate_offer(offer)
            if any(offer[k] != self.state["selected_offer"][k] for k in ("id", "total_amount", "total_currency")):
                raise ValueError("quote_changed_stop")
            # Local simulation records exposure before the external request.
            # This processor does NOT fence Duffel or prove its population complete.
            proc = FencedProcessor("local-admission-not-duffel", self.private / "processor.db")
            coord = PersistentCoordinator("flight", CAP_MINOR, self.private / "flight.db")
            proc.open_epoch(self.state["reference"])
            coord.reserve_quote("flight-quote", 1, amount)
            coord.submit(proc, self.state["reference"], "flight-quote", 1, self.state["reference"])
            coord.close(); proc.close()
            self.state["retained_cap_minor"] = amount
            self.save()
            passenger = {"id": offer["passengers"][0]["id"], "given_name": "Trustbound", "family_name": "Sandbox",
                         "title": "mr", "gender": "m", "born_on": "1990-01-01",
                         "email": "trustbound-sandbox@example.com", "phone_number": "+12025550123"}
            return self.request(stage, "POST", "/air/orders", {
                "type": "instant", "selected_offers": [offer["id"]], "passengers": [passenger],
                "payments": [{"type": "balance", "currency": "USD", "amount": offer["total_amount"]}],
                "metadata": {"trustbound_reference": self.state["reference"]}}, timeout=130)
        if stage == "lookup-by-offer":
            offer = self.state["selected_offer"]
            return self.request(stage, "GET", "/air/orders?" + urlencode({"offer_id": offer["id"], "limit": 200}))
        if stage == "recover":
            if not (self.private / "book-request.json").exists():
                raise ValueError("booking_attempt_required")
            result = json.loads((self.root / "lookup-by-offer-result.json").read_text())
            candidates = self.previous("lookup-by-offer")
            # Missing and ambiguous matches remain unknown; never infer no-effect.
            if result.get("has_more") is not False or len(candidates) != 1:
                raise ValueError("recovery_not_unique_or_incomplete")
            order = candidates[0]
            quote = self.state["selected_offer"]
            if (order.get("live_mode") is not False
                    or order.get("metadata", {}).get("trustbound_reference") != self.state["reference"]
                    or any(order.get(k) != quote[k] for k in ("total_amount", "total_currency"))):
                raise ValueError("recovery_binding_mismatch")
            identifier(order.get("id"), "ord")
            with (self.private / "recovered-order.json").open("x") as f:
                json.dump(order, f)
            result = {"stage": stage, "source": "fresh_scoped_provider_lookup", "record": projection(order),
                      "payment_state_changed": False, "epoch_completeness_established": False}
            (self.root / "recover-result.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            return order
        order_id = self.own_order()
        if stage in {"retrieve", "retrieve-final"}:
            return self.request(stage, "GET", "/air/orders/" + order_id)
        if stage in {"payments", "payments-final"}:
            return self.request(stage, "GET", "/air/payments?" + urlencode({"order_id": order_id, "limit": 200}))
        if stage == "cancel-quote":
            order = self.previous("retrieve")
            if order["id"] != order_id or order.get("live_mode") is not False or "cancel" not in order.get("available_actions", []):
                raise ValueError("own_order_not_cancellable")
            return self.request(stage, "POST", "/air/order_cancellations", {"order_id": order_id}, timeout=130)
        if stage == "cancel-confirm":
            cancellation = self.previous("cancel-quote")
            if cancellation.get("live_mode") is not False or cancellation["order_id"] != order_id:
                raise ValueError("own_test_cancellation_required")
            cid = identifier(cancellation["id"], "ore")
            return self.request(stage, "POST", "/air/order_cancellations/" + cid + "/actions/confirm", timeout=130)
        raise ValueError("unsupported_stage")


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["search", "refresh-offer", "book", "lookup-by-offer", "recover", "retrieve",
                                         "payments", "cancel-quote", "cancel-confirm", "retrieve-final", "payments-final"])
    parser.add_argument("--discard-book-reply", action="store_true")
    args = parser.parse_args()
    if args.discard_book_reply and args.stage != "book":
        parser.error("reply discard applies only to book")
    Probe(os.environ["TRUSTBOUND_DUFFEL_RUN_DIR"],
          Path(os.environ["TRUSTBOUND_DUFFEL_KEY_FILE"]).read_text().strip(),
          discard_book_reply=args.discard_book_reply).run(args.stage)
