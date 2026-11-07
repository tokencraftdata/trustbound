"""Read-only Stripe test-mode observations. Not an epoch completeness oracle.

No create, confirm, capture, cancel or refund endpoints are implemented. The
transport defaults to the real HTTPS endpoint; unit tests replace it explicitly.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


STRIPE_VERSION = "2026-10-28.endive"


class ObservationError(RuntimeError):
    """Observation unavailable or unsuitable. Never implies no payment."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ObservationError("redirect_rejected")


def _get_json(request: Request, timeout: float) -> dict:
    try:
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            raw = response.read(1_048_577)
            if len(raw) > 1_048_576:
                raise ObservationError("response_too_large")
            return json.loads(raw)
    except HTTPError as exc:
        # Do not expose provider error bodies, authentication or client secrets.
        raise ObservationError(f"stripe_http_{exc.code}") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise ObservationError("stripe_observation_unavailable") from None


class StripeSandboxObserver:
    def __init__(self, api_key: str, *, transport=None, timeout: float = 10):
        if not re.fullmatch(r"(?:sk|rk|rkcs)_test_[A-Za-z0-9]+", api_key):
            raise ValueError("test_mode_key_required")
        if not 0 < timeout <= 30:
            raise ValueError("invalid_timeout")
        self._api_key = api_key
        self._transport = transport or _get_json
        self._timeout = timeout

    def retrieve(self, payment_id: str) -> dict:
        if not re.fullmatch(r"pi_[A-Za-z0-9]+", payment_id):
            raise ValueError("invalid_payment_intent_id")
        request = Request(
            f"https://api.stripe.com/v1/payment_intents/{payment_id}",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Stripe-Version": STRIPE_VERSION,
            },
            method="GET",
        )
        try:
            data = self._transport(request, self._timeout)
        except (TimeoutError, OSError):
            raise ObservationError("stripe_observation_unavailable") from None
        if not isinstance(data, dict) or data.get("livemode") is not False:
            raise ObservationError("non_sandbox_or_missing_mode")
        if data.get("id") != payment_id or data.get("object") != "payment_intent":
            raise ObservationError("payment_identity_mismatch")
        for field in ("amount", "amount_received", "amount_capturable"):
            if type(data.get(field)) is not int or data[field] < 0:
                raise ObservationError("invalid_payment_amounts")
        currency = data.get("currency")
        if not isinstance(currency, str) or not re.fullmatch("[a-z]{3}", currency):
            raise ObservationError("invalid_currency")
        provider_status = data.get("status")
        if provider_status not in {
            "requires_payment_method", "requires_confirmation", "requires_action",
            "processing", "requires_capture", "canceled", "succeeded",
        }:
            raise ObservationError("unknown_payment_status")
        status = "uncertain"
        if (provider_status == "succeeded" and data["amount_received"] == data["amount"]
                and data["amount_capturable"] == 0):
            status = "confirmed"
        elif (provider_status == "canceled" and data["amount_received"] == 0
                and data["amount_capturable"] == 0):
            status = "released"
        # Whitelist output; never persist the full response or client_secret.
        return {
            "payment_id": payment_id, "amount_minor": data["amount"],
            "currency": currency, "status": status,
            "provider_status": provider_status,
            "received_minor": data["amount_received"],
            "capturable_minor": data["amount_capturable"],
            "livemode": False, "stripe_version": STRIPE_VERSION,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "scope": "known_payment_intent_only",
        }
