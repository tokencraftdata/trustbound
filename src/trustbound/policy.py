"""Itinerary-level policy and evidence commitments."""

from __future__ import annotations

import hashlib
import json

import rfc8785

from .models import BookingFact, ItineraryManifest


def itinerary_violations(manifest: ItineraryManifest, fact: BookingFact) -> list[str]:
    violations: list[str] = []
    if fact.itinerary_id != manifest.itinerary_id:
        violations.append("itinerary_id")
    if fact.currency != manifest.currency:
        violations.append("currency")
    if fact.merchant_id not in manifest.allowed_merchants:
        violations.append("merchant")
    if manifest.refundable_required and not fact.refundable:
        violations.append("refundability")

    if fact.leg == "flight_out":
        expected = (
            manifest.outbound_origin,
            manifest.outbound_destination,
            manifest.outbound_arrival,
        )
        if (fact.origin, fact.destination, fact.end) != expected:
            violations.append("outbound_route_or_time")
    elif fact.leg == "hotel":
        expected = (manifest.hotel_city, manifest.hotel_checkin, manifest.hotel_checkout)
        if (fact.city, fact.start, fact.end) != expected:
            violations.append("hotel_city_or_dates")
    elif fact.leg == "flight_return":
        expected = (
            manifest.return_origin,
            manifest.return_destination,
            manifest.return_departure,
        )
        if (fact.origin, fact.destination, fact.start) != expected:
            violations.append("return_route_or_time")
    else:
        violations.append("unknown_leg")
    return violations


def evidence_commitment(
    manifest: ItineraryManifest,
    fact: BookingFact,
    checkout_hash: str,
    previous: str | None = None,
) -> str:
    payload = {
        "manifest": manifest.as_dict(),
        "booking": fact.as_dict(),
        "checkout_hash": checkout_hash,
        "previous": previous,
    }
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


def explain_manifest(manifest: ItineraryManifest) -> str:
    return json.dumps(manifest.as_dict(), sort_keys=True, indent=2)

