"""Read-only same-account sandbox reconciliation, not independent-issuer proof."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.request import Request, build_opener

from trustbound.sandbox_observer import StripeSandboxObserver, _NoRedirect, STRIPE_VERSION


def get_list(key, resource, fields):
    StripeSandboxObserver(key)
    if resource not in {"payment_intents", "charges"}:
        raise ValueError("unsupported_resource")
    req = Request("https://api.stripe.com/v1/" + resource + "?limit=100", headers={
        "Authorization": "Bearer " + key, "Stripe-Version": STRIPE_VERSION,
    })
    with build_opener(_NoRedirect()).open(req, timeout=10) as response:
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise RuntimeError("response_too_large")
        data = json.loads(raw)
        request_id = response.headers.get("Request-Id")
    if data.get("object") != "list" or data.get("has_more") is not False:
        raise RuntimeError("single_page_scope_exceeded_or_invalid_response")
    if any(row.get("livemode") is not False for row in data["data"]):
        raise RuntimeError("non_sandbox_response")
    return {"endpoint": "/v1/" + resource, "request_id": request_id,
            "observed_at": datetime.now(timezone.utc).isoformat(), "has_more": False,
            "records": [{field: row.get(field) for field in fields} for row in data["data"]]}


def compare(payments, charges):
    payment_rows, charge_rows = payments["records"], charges["records"]
    comparisons = []
    for payment in payment_rows:
        related = [row for row in charge_rows if row["payment_intent"] == payment["id"]]
        captured = sum(row["amount_captured"] for row in related)
        comparisons.append({"payment_id": payment["id"], "intent_received_minor": payment["amount_received"],
                            "charges_captured_minor": captured,
                            "matches": captured == payment["amount_received"] and all(row["currency"] == payment["currency"] for row in related)})
    unknown = sorted(row["id"] for row in charge_rows if row["payment_intent"] not in {p["id"] for p in payment_rows})
    return {"payments": payments, "charges": charges, "comparisons": comparisons,
            "all_compared_amounts_match": bool(comparisons) and not unknown and all(row["matches"] for row in comparisons),
            "unmatched_charge_ids": unknown,
            "payment_states": dict(Counter(row["status"] for row in payment_rows)),
            "epoch_completeness_established": False,
            "scope": "single_page_views_of_same_processor_not_atomic_or_independent_issuers"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("TRUSTBOUND_STRIPE_TEST_KEY", "")
    payments = get_list(key, "payment_intents", ["id", "livemode", "amount", "currency", "status", "amount_received", "amount_capturable", "latest_charge"])
    charges = get_list(key, "charges", ["id", "livemode", "amount", "currency", "status", "captured", "amount_captured", "amount_refunded", "paid", "payment_intent", "balance_transaction"])
    result = compare(payments, charges)
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ["all_compared_amounts_match", "payment_states", "epoch_completeness_established"]}))
    return 0 if result["all_compared_amounts_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
