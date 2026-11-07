"""Recheck sanitized experiment evidence offline; this does not authenticate it."""
import argparse
from decimal import Decimal
import json
from pathlib import Path


def check(root):
    stages = ["search", "refresh-offer", "book", "retrieve", "lookup-by-offer",
              "payments", "cancel-quote", "cancel-confirm", "retrieve-final", "payments-final"]
    records = {s: json.loads((root / (s + "-result.json")).read_text()) for s in stages}
    offer = records["refresh-offer"]["record"]
    book = records["book"]["record"]
    retrieved = records["retrieve"]["record"]
    final = records["retrieve-final"]["record"]
    payments = records["payments"]["records"]
    final_payments = records["payments-final"]["records"]
    cancellation = records["cancel-confirm"]["record"]
    lookup = records["lookup-by-offer"]["records"]
    local = json.loads((root / "local-exposure.json").read_text())
    amount = int(Decimal(book["total_amount"]) * 100)
    checks = {
        "ten_http_successes": all(r["http_status"] in (200, 201) for r in records.values()),
        "all_projected_objects_test_mode": all(obj.get("live_mode") is False for r in records.values()
            for obj in ([r["record"]] if "record" in r else r.get("records", []))),
        "synthetic_airline": offer["owner"]["name"] == "Duffel Airways" and offer["owner"]["iata_code"] == "ZZ",
        "booked_quote_matches": all(book[k] == offer[k] for k in ("total_amount", "total_currency")),
        "fresh_order_matches": all(retrieved[k] == book[k] for k in ("id", "total_amount", "total_currency", "metadata")),
        "scoped_order_lookup_matches": len(lookup) == 1 and lookup[0]["id"] == book["id"] and not records["lookup-by-offer"]["has_more"],
        "known_payment_matches": len(payments) == 1 and payments[0]["order_id"] == book["id"]
            and payments[0]["status"] == "succeeded" and payments[0]["amount"] == book["total_amount"]
            and payments[0]["currency"] == book["total_currency"] and not records["payments"]["has_more"],
        "cancellation_binds_own_order": cancellation["order_id"] == book["id"] and bool(cancellation["confirmed_at"]),
        "refund_report_matches": cancellation["refund_amount"] == book["total_amount"]
            and cancellation["refund_currency"] == book["total_currency"] and cancellation["refund_to"] == "balance",
        "fresh_order_cancelled": final["id"] == book["id"] and final["cancelled_at"] == cancellation["confirmed_at"],
        "original_payment_remains_succeeded": final_payments == payments and not records["payments-final"]["has_more"],
        "local_exposure_retained": local["liability_minor"] == amount and len(local["quotes"]) == 1
            and local["quotes"][0][3] == "uncertain",
        "no_epoch_completeness_claim": all(r["epoch_completeness_established"] is False for r in records.values()),
    }
    return {"experiment_date_local": "2026-11-01", "timezone": "America/Los_Angeles", "api": "Duffel REST v2",
            "http_calls": len(stages), "checks": checks, "passed": sum(checks.values()),
            "failed": sum(not v for v in checks.values()), "amount_minor": amount, "currency": book["total_currency"],
            "order_id": book["id"], "retained_exposure_minor": local["liability_minor"],
            "epoch_completeness_established": False, "independent_observer_evidence": False,
            "processor_refund_independently_verified": False, "ucp_ap2_counterparty_integration": False,
            "production_execution": False, "authenticated_evidence_bundle": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check(args.directory)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
    raise SystemExit(1 if report["failed"] else 0)
