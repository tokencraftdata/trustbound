"""UCP checkout construction and AP2 mandate issuance/verification.

This module imports the official UCP Python models and Google's AP2 SDK. It is
not a reimplementation of their mandate formats.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import rfc8785
from ap2.sdk.checkout_mandate_chain import CheckoutMandateChain
from ap2.sdk.constraints import MandateContext
from ap2.sdk.generated.checkout_mandate import CheckoutMandate
from ap2.sdk.generated.open_checkout_mandate import (
    AllowedMerchants,
    Item,
    LineItemRequirements,
    LineItems,
    OpenCheckoutMandate,
)
from ap2.sdk.generated.open_payment_mandate import (
    AllowedPayees,
    AmountRange,
    Budget,
    OpenPaymentMandate,
)
from ap2.sdk.generated.payment_mandate import PaymentMandate
from ap2.sdk.generated.types.amount import Amount
from ap2.sdk.generated.types.merchant import Merchant
from ap2.sdk.generated.types.payment_instrument import PaymentInstrument
from ap2.sdk.jwt_helper import create_jwt, verify_jwt
from ap2.sdk.mandate import MandateClient
from ap2.sdk.payment_mandate_chain import PaymentMandateChain
from ap2.sdk.utils import b64url_encode, compute_sha256_b64url
from jwcrypto.jwk import JWK
from jwcrypto.jws import JWS
from cryptography.hazmat.primitives.asymmetric import ec
from ucp_sdk.models.schemas.common.payment_ap2_mandate import Checkout as UcpAp2Checkout
from ucp_sdk.models.schemas.shopping.checkout_complete_request import (
    CheckoutCompleteRequest,
)

from .models import BookingFact, ItineraryManifest


@dataclass
class ProtocolArtifacts:
    fact: BookingFact
    checkout: dict[str, Any]
    checkout_jwt: str
    checkout_hash: str
    checkout_mandate: str
    payment_mandate: str
    completion_request: dict[str, Any]


@dataclass(frozen=True)
class ProtocolVerification:
    valid: bool
    reason: str
    checkout_hash: str | None = None


def _key(kid: str) -> JWK:
    raw = JWK.from_pyca(ec.generate_private_key(ec.SECP256R1()))
    material = json.loads(raw.export())
    material["kid"] = kid
    return JWK.from_json(json.dumps(material))


def _public(key: JWK) -> JWK:
    return JWK.from_json(key.export_public())


def sign_detached_jws(payload: dict[str, Any], key: JWK, kid: str) -> str:
    canonical = rfc8785.dumps(payload)
    jws = JWS(canonical)
    jws.add_signature(
        key,
        alg="ES256",
        protected=json.dumps({"alg": "ES256", "kid": kid}, separators=(",", ":")),
    )
    protected, encoded_payload, signature = jws.serialize(compact=True).split(".")
    assert encoded_payload == b64url_encode(canonical)
    return f"{protected}..{signature}"


def verify_detached_jws(token: str, payload: dict[str, Any], key: JWK) -> None:
    protected, empty, signature = token.split(".")
    if empty:
        raise ValueError("merchant authorization is not detached")
    attached = f"{protected}.{b64url_encode(rfc8785.dumps(payload))}.{signature}"
    jws = JWS()
    jws.deserialize(attached)
    header = jws.jose_header
    if header.get("alg") != "ES256" or not header.get("kid"):
        raise ValueError("unsupported or unkeyed merchant signature")
    jws.verify(key)


class ProtocolHarness:
    """Issues and verifies real AP2 SDK artifacts in UCP-shaped messages."""

    ucp_version = "2026-08-25"

    def __init__(self, manifest: ItineraryManifest) -> None:
        self.manifest = manifest
        self.mandates = MandateClient()
        self.user_issuer_key = _key("user-issuer-1")
        self.agent_key = _key("shopping-agent-1")
        self.merchant_keys = {merchant: _key(f"{merchant}-signing-1") for merchant in manifest.allowed_merchants}

    def _checkout(self, fact: BookingFact) -> tuple[dict[str, Any], str, str]:
        travel = {
            "itinerary_id": fact.itinerary_id,
            "leg": fact.leg,
            "origin": fact.origin,
            "destination": fact.destination,
            "start": fact.start,
            "end": fact.end,
            "city": fact.city,
            "refundable": fact.refundable,
        }
        total = [{"type": "subtotal", "amount": fact.amount_minor}, {"type": "total", "amount": fact.amount_minor}]
        checkout: dict[str, Any] = {
            "ucp": {"version": self.ucp_version, "status": "success", "payment_handlers": {}},
            "id": fact.checkout_id,
            "merchant": {"id": fact.merchant_id, "name": fact.merchant_name},
            "line_items": [{
                "id": f"line-{fact.transaction_id}",
                "item": {"id": fact.item_id, "title": fact.title, "price": fact.amount_minor, "travel": travel},
                "quantity": 1,
                "totals": total,
            }],
            "status": "ready_for_complete",
            "currency": fact.currency,
            "totals": total,
            "links": [{"type": "terms_of_service", "url": "https://example.test/terms"}],
        }
        merchant_key = self.merchant_keys[fact.merchant_id]
        checkout["ap2"] = {
            "merchant_authorization": sign_detached_jws(checkout, merchant_key, f"{fact.merchant_id}-signing-1")
        }
        UcpAp2Checkout.model_validate(checkout)
        checkout_jwt = create_jwt(
            {"alg": "ES256", "typ": "JWT", "kid": f"{fact.merchant_id}-signing-1"},
            checkout,
            merchant_key,
        )
        return checkout, checkout_jwt, compute_sha256_b64url(checkout_jwt)

    def issue(self, fact: BookingFact) -> ProtocolArtifacts:
        checkout, checkout_jwt, checkout_hash = self._checkout(fact)
        now = int(time.time())
        agent_public = json.loads(self.agent_key.export_public())
        merchant = Merchant(id=fact.merchant_id, name=fact.merchant_name)

        open_checkout = self.mandates.create(
            payloads=[OpenCheckoutMandate(
                constraints=[
                    AllowedMerchants(allowed=[merchant]),
                    LineItems(items=[LineItemRequirements(
                        id=f"required-{fact.leg}",
                        acceptable_items=[Item(id=fact.item_id, title=fact.title)],
                        quantity=1,
                    )]),
                ],
                cnf={"jwk": agent_public},
                iat=now,
                exp=now + 3600,
            )],
            issuer_key=self.user_issuer_key,
        )
        checkout_mandate = self.mandates.present(
            holder_key=self.agent_key,
            mandate_token=open_checkout,
            payloads=[CheckoutMandate(
                checkout_jwt=checkout_jwt,
                checkout_hash=checkout_hash,
                iat=now,
                exp=now + 3600,
            )],
            nonce=fact.checkout_id,
            aud=fact.merchant_id,
        )

        open_payment = self.mandates.create(
            payloads=[OpenPaymentMandate(
                constraints=[
                    AllowedPayees(allowed=[merchant]),
                    AmountRange(currency=fact.currency, min=0, max=self.manifest.budget_minor),
                    Budget(max=self.manifest.budget_minor / 100, currency=fact.currency),
                ],
                cnf={"jwk": agent_public},
                iat=now,
                exp=now + 3600,
            )],
            issuer_key=self.user_issuer_key,
        )
        payment_mandate = self.mandates.present(
            holder_key=self.agent_key,
            mandate_token=open_payment,
            payloads=[PaymentMandate(
                transaction_id=checkout_hash,
                payee=merchant,
                payment_amount=Amount(amount=fact.amount_minor, currency=fact.currency),
                payment_instrument=PaymentInstrument(id="card-token-1", type="card", description="test credential"),
                iat=now,
                exp=now + 3600,
            )],
            nonce=fact.transaction_id,
            aud="payment-processor",
        )
        completion_request = {
            "payment": {"instruments": [{
                "id": "instrument-1",
                "handler_id": "test-handler",
                "type": "card",
                "selected": True,
                "credential": {"type": "token", "token": payment_mandate},
            }]},
            "ap2": {"checkout_mandate": checkout_mandate},
        }
        CheckoutCompleteRequest.model_validate(completion_request)
        return ProtocolArtifacts(
            fact=fact,
            checkout=checkout,
            checkout_jwt=checkout_jwt,
            checkout_hash=checkout_hash,
            checkout_mandate=checkout_mandate,
            payment_mandate=payment_mandate,
            completion_request=completion_request,
        )

    def verify(self, artifacts: ProtocolArtifacts, spent_minor: int = 0, total_uses: int = 0) -> ProtocolVerification:
        try:
            UcpAp2Checkout.model_validate(artifacts.checkout)
            CheckoutCompleteRequest.model_validate(artifacts.completion_request)
            merchant_id = artifacts.fact.merchant_id
            merchant_key = self.merchant_keys[merchant_id]
            ap2 = artifacts.checkout.get("ap2") or {}
            detached_payload = {key: value for key, value in artifacts.checkout.items() if key != "ap2"}
            verify_detached_jws(ap2["merchant_authorization"], detached_payload, _public(merchant_key))
            jwt_payload = verify_jwt(artifacts.checkout_jwt, _public(merchant_key))
            if jwt_payload != artifacts.checkout:
                return ProtocolVerification(False, "checkout_jwt_payload_mismatch")
            actual_hash = compute_sha256_b64url(artifacts.checkout_jwt)
            if actual_hash != artifacts.checkout_hash:
                return ProtocolVerification(False, "checkout_hash_mismatch")

            checkout_payloads = self.mandates.verify(
                artifacts.checkout_mandate,
                lambda _token: _public(self.user_issuer_key),
                expected_aud=merchant_id,
                expected_nonce=artifacts.fact.checkout_id,
            )
            checkout_chain = CheckoutMandateChain.parse(checkout_payloads)
            violations = checkout_chain.verify(
                expected_checkout_hash=actual_hash,
                checkout_jwt=artifacts.checkout_jwt,
            )
            if violations:
                return ProtocolVerification(False, "checkout:" + "|".join(violations))

            payment_payloads = self.mandates.verify(
                artifacts.payment_mandate,
                lambda _token: _public(self.user_issuer_key),
                expected_aud="payment-processor",
                expected_nonce=artifacts.fact.transaction_id,
            )
            payment_chain = PaymentMandateChain.parse(payment_payloads)
            violations = payment_chain.verify(
                expected_transaction_id=actual_hash,
                mandate_context=MandateContext(total_amount=spent_minor, total_uses=total_uses),
            )
            if violations:
                return ProtocolVerification(False, "payment:" + "|".join(violations))
            checkout_total = next(item["amount"] for item in artifacts.checkout["totals"] if item["type"] == "total")
            if payment_chain.closed_mandate.payment_amount.amount != checkout_total:
                return ProtocolVerification(False, "payment_checkout_amount_mismatch")
            return ProtocolVerification(True, "verified", actual_hash)
        except Exception as exc:  # verifier must fail closed on malformed evidence
            return ProtocolVerification(False, f"protocol_error:{type(exc).__name__}")
