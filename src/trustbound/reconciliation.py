"""Compare explicitly supplied travel records; never infer global completeness.

One booking and one payment per leg, same currency/amount, no split payments,
fees, FX, refunds or direct-provider billing. Other architectures need adapters.
Input provenance and exhaustive provider population are external obligations.
"""
from __future__ import annotations

import re


def compare_records(expected: list[dict], bookings: list[dict], payments: list[dict]) -> dict:
    errors: list[str] = []

    def index(rows, fields, label):
        indexed = {}
        for row in rows:
            if not isinstance(row, dict) or any(
                not isinstance(row.get(f), str) or not row[f] for f in fields
            ):
                errors.append(f"{label}:invalid_identity")
                continue
            key = tuple(row[f] for f in fields)
            if key in indexed:
                errors.append(f"{label}:duplicate_identity")
            indexed[key] = row
        return indexed

    locals_by_leg = index(expected, ("leg",), "local")
    if set(locals_by_leg) != {("flight",), ("hotel",)}:
        errors.append("local:flight_and_hotel_required")
    booking_index = index(bookings, ("booking_provider", "booking_id"), "booking")
    payment_index = index(payments, ("payment_id",), "payment")
    expected_bookings, expected_payments = set(), set()
    for (leg,), local in locals_by_leg.items():
        required = ("booking_provider", "booking_id", "payment_id", "currency")
        if any(not isinstance(local.get(f), str) or not local[f] for f in required):
            errors.append(f"{leg}:invalid_local_binding")
            continue
        if type(local.get("amount_minor")) is not int or local["amount_minor"] < 0:
            errors.append(f"{leg}:invalid_local_amount")
        if not re.fullmatch("[a-z]{3}", local["currency"]):
            errors.append(f"{leg}:invalid_local_currency")
        bk = (local["booking_provider"], local["booking_id"])
        pk = (local["payment_id"],)
        if bk in expected_bookings or pk in expected_payments:
            errors.append(f"{leg}:shared_identity_unsupported")
        expected_bookings.add(bk)
        expected_payments.add(pk)
        booking, payment = booking_index.get(bk), payment_index.get(pk)
        if booking is None:
            errors.append(f"{leg}:booking_missing")
        if payment is None:
            errors.append(f"{leg}:payment_missing")
        for label, external in (("booking", booking), ("payment", payment)):
            if external is None:
                continue
            if external.get("livemode") is not False:
                errors.append(f"{leg}:{label}_not_sandbox")
            for field in ("amount_minor", "currency", "payment_id"):
                if external.get(field) != local.get(field) or type(external.get(field)) is not type(local.get(field)):
                    errors.append(f"{leg}:{label}_{field}_mismatch")
            local_status = local.get(f"{label}_status")
            allowed = {"confirmed", "canceled"} if label == "booking" else {"confirmed", "released"}
            if external.get("status") not in allowed:
                errors.append(f"{leg}:{label}_unresolved")
            if local_status != external.get("status"):
                errors.append(f"{leg}:{label}_status_mismatch")
        if booking and payment:
            if (booking.get("status"), payment.get("status")) not in {
                ("confirmed", "confirmed"), ("canceled", "released")
            }:
                errors.append(f"{leg}:partial_failure_or_unresolved")
    if set(booking_index) - expected_bookings:
        errors.append("booking:unexpected_records")
    if set(payment_index) - expected_payments:
        errors.append("payment:unexpected_records")
    return {
        "records_match": not errors,
        "errors": errors,
        "epoch_completeness_established": False,
        "provenance_authenticated": False,
        "scope": "supplied_two_leg_records_only",
        "local_record_count": len(expected),
        "booking_record_count": len(bookings),
        "payment_record_count": len(payments),
    }
