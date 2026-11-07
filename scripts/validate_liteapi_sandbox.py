"""Staged shared-demo sandbox probe. No unfiltered booking reads or blind retries."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
import uuid
from decimal import Decimal
from trustbound.coordinator import PersistentCoordinator
from trustbound.epoch import FencedProcessor

ROOT = Path(os.environ["TRUSTBOUND_LITEAPI_RUN_DIR"]).resolve()
PRIVATE = ROOT / "private"
os.umask(0o077)
PRIVATE.mkdir(mode=0o700, parents=True, exist_ok=True)
KEY = os.environ.get("LITEAPI_API_KEY", "")
if not re.fullmatch(r"(?:sand|sandbox)_[A-Za-z0-9-]+", KEY):
    raise SystemExit("Sandbox-only key required")
STATE = PRIVATE / "state.json"
if STATE.exists():
    state = json.loads(STATE.read_text())
else:
    state = {"clientReference": "trustbound-" + uuid.uuid4().hex}
    STATE.write_text(json.dumps(state))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise RuntimeError("redirect_rejected")

def request(stage, method, host, path, body=None, timeout=20):
    if host not in {"api.liteapi.travel", "book.liteapi.travel"}:
        raise ValueError("unsupported_host")
    journal = PRIVATE / (stage + "-request.json")
    if journal.exists():
        raise RuntimeError("stage_already_attempted_inspect_before_retry")
    journal.write_text(json.dumps({"method": method, "host": host, "path": path, "body": body, "outcome": "unknown"}))
    req = Request("https://" + host + "/v3.0" + path,
                  data=None if body is None else json.dumps(body).encode(), method=method,
                  headers={"X-API-Key": KEY, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        try:
            response = build_opener(NoRedirect()).open(req, timeout=timeout)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise RuntimeError("response_too_large")
            data = json.loads(raw) if raw else {}
            code = response.code
            request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
    except (URLError, TimeoutError, OSError, ValueError):
        result = {"stage": stage, "outcome": "unknown", "retry_performed": False}
        (ROOT / (stage + "-result.json")).write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
        raise SystemExit(1)
    (PRIVATE / (stage + "-response.json")).write_text(json.dumps(data))
    result = {"stage": stage, "method": method, "endpoint": "https://" + host + "/v3.0" + path,
              "http_status": code, "request_id": request_id,
              "observed_at": datetime.now(timezone.utc).isoformat(),
              "credential_scope": os.environ.get("TRUSTBOUND_LITEAPI_CREDENTIAL_SCOPE", "operator_supplied_sandbox"), "epoch_completeness_established": False}
    if isinstance(data.get("data"), list):
        result["record_count"] = len(data["data"])
    if "sandbox" in data:
        result["sandbox_marker"] = data["sandbox"]
    if isinstance(data.get("data"), dict):
        result["booking_projection"] = {k: data["data"].get(k) for k in
            ("bookingId", "clientReference", "status", "price", "currency", "cancellation_fee", "refund_amount")
            if k in data["data"]}
    result["response_fields"] = sorted(data)
    if isinstance(data.get("error"), dict):
        result["error_code"] = data["error"].get("code")
        # Sanitized provider diagnostic, not a raw response dump.
        message = str(data["error"].get("message", ""))
        result["safe_error_message"] = re.sub(r"(?:sand|sandbox|prod)_\S+|https?://\S+|\S+@\S+", "[redacted]", message)
    (ROOT / (stage + "-result.json")).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return code, data

stage = sys.argv[1]
if stage == "lookup-before":
    request(stage, "GET", "book.liteapi.travel", "/bookings?" + urlencode({"clientReference": state["clientReference"]}))
elif stage == "rates":
    request(stage, "POST", "api.liteapi.travel", "/hotels/rates", {
        "checkin": "2026-12-01", "checkout": "2026-12-02", "currency": "USD",
        "guestNationality": "US", "occupancies": [{"adults": 1}],
        "countryCode": "US", "cityName": "New York", "limit": 2, "maxRatesPerHotel": 2,
        "timeout": 8,
    })
elif stage == "prebook":
    rates = json.loads((PRIVATE / "rates-response.json").read_text())
    if rates.get("sandbox") is not True:
        raise SystemExit("Sandbox marker required")
    offer = rates["data"][0]["roomTypes"][0]
    amount = offer["offerRetailRate"]
    if amount["currency"] != "USD" or not 0 < amount["amount"] <= 1000:
        raise SystemExit("Synthetic quote exceeds probe cap")
    state["search_amount"] = amount
    STATE.write_text(json.dumps(state))
    request(stage, "POST", "book.liteapi.travel", "/rates/prebook", {
        "offerId": offer["offerId"], "usePaymentSdk": False,
    }, timeout=40)
elif stage == "book":
    prebook = json.loads((PRIVATE / "prebook-response.json").read_text())
    p = prebook["data"]
    if prebook.get("sandbox") is not True or p["currency"] != "USD":
        raise SystemExit("Sandbox marker and USD required")
    amount = Decimal(str(p["price"])) * 100
    if amount != amount.to_integral_value() or not 0 < amount <= 100000:
        raise SystemExit("Synthetic quote exceeds probe cap")
    if p["price"] != state["search_amount"]["amount"]:
        raise SystemExit("Quote changed; stop before booking")
    processor = FencedProcessor("local-admission-not-liteapi", PRIVATE / "processor.db")
    processor.open_epoch(state["clientReference"])
    coordinator = PersistentCoordinator("hotel", 100000, PRIVATE / "hotel.db")
    coordinator.reserve_quote("hotel-quote", 1, int(amount))
    coordinator.submit(processor, state["clientReference"], "hotel-quote", 1, state["clientReference"])
    state["retained_cap_minor"] = int(amount)
    STATE.write_text(json.dumps(state))
    coordinator.close()
    processor.close()
    synthetic = {"firstName": "TrustBound", "lastName": "Sandbox", "email": "trustbound-sandbox@example.com"}
    request(stage, "POST", "book.liteapi.travel", "/rates/book", {
        "prebookId": p["prebookId"], "clientReference": state["clientReference"],
        "holder": synthetic, "guests": [{**synthetic, "occupancyNumber": 1}],
        "payment": {"method": "ACC_CREDIT_CARD"},
    }, timeout=130)
elif stage in {"lookup-after", "lookup-final"}:
    request(stage, "GET", "book.liteapi.travel", "/bookings?" + urlencode({"clientReference": state["clientReference"]}))
elif stage in {"retrieve", "cancel", "retrieve-final"}:
    booking = json.loads((PRIVATE / "book-response.json").read_text())["data"]
    if booking.get("clientReference") != state["clientReference"]:
        raise SystemExit("Own booking reference binding required")
    booking_id = booking["bookingId"]
    if not re.fullmatch(r"[A-Za-z0-9_-]+", booking_id):
        raise SystemExit("Invalid booking ID")
    request(stage, "PUT" if stage == "cancel" else "GET", "book.liteapi.travel", "/bookings/" + booking_id, timeout=40)
else:
    raise SystemExit("Unsupported stage")

