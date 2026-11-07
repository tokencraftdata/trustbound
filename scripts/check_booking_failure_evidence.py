"""Offline checks of saved controlled-failure evidence. No API calls or secrets."""
import argparse
from decimal import Decimal
import json
from pathlib import Path


def read(root, path):
    return json.loads((root / path).read_text())


def evaluate_inventory(manifest, inventory):
    """Conventional reconciliation and TrustBound use the same visible evidence.

    No experiment oracle, second-client state, or provider-wide truth is an input.
    The historical baseline inventory is excluded explicitly by the caller.
    """
    conventional = sorted(set(inventory) - set(manifest))
    trustbound = sorted(oid for oid in inventory if oid not in manifest)
    return {"conventional_unmanifested": conventional, "trustbound_unmanifested": trustbound,
            "equal_information_agrees": conventional == trustbound,
            "exact_closure_established": False, "closure_prerequisite_missing": "authoritative_admission_fence"}


def check(root):
    drop = read(root, "primary/book-result.json")
    retry = read(root, "primary/restart-duplicate-result.json")
    recovered = read(root, "primary/recover-result.json")["record"]
    primary = read(root, "primary/retrieve-result.json")["record"]
    payment = read(root, "primary/payments-result.json")["records"]
    comparison = read(root, "audit/comparison.json")
    before = read(root, "audit/inventory-before.json")
    after = read(root, "audit/inventory-after.json")
    local = read(root, "local-exposure.json")
    before_ids = {r["id"] for r in before["records"]}
    evidence_ids = {r["id"] for r in after["records"]} - (before_ids - {primary["id"]})
    baseline = evaluate_inventory({primary["id"]}, evidence_ids)
    known_match = len(payment) == 1 and payment[0]["order_id"] == primary["id"] and payment[0]["status"] == "succeeded" and payment[0]["amount"] == primary["total_amount"]
    checks = {
        "client_response_discard_recorded": drop.get("fault_injection") == "client_discard_after_response_read_before_parse" and drop.get("outcome") == "unknown",
        "discarded_reply_not_used_for_recovery": retry["raw_book_response_absent"],
        "restart_retry_blocked_locally": retry["blocked_before_dispatch"] and retry["request_journal_unchanged"] and not retry["remote_duplicate_sent"],
        "uncertain_exposure_survived_restart": retry["local_quote_rows"] == [[18107, "uncertain"]],
        "recovered_order_matches_fresh_read": all(recovered[k] == primary[k] for k in ("id", "metadata", "total_amount", "total_currency")),
        "known_order_payment_reconciles": known_match,
        "inventory_detects_unmanifested_order": len(comparison["new_unmanifested_order_ids"]) == 1 and bool(baseline["conventional_unmanifested"]),
        "comparison_matches_inventory_difference": baseline["conventional_unmanifested"] == comparison["new_unmanifested_order_ids"],
        "unmanifested_payment_succeeded": len(comparison["observed_unmanifested_payments"]) == 1 and comparison["observed_unmanifested_payments"][0]["status"] == "succeeded",
        "audit_did_not_read_second_client_journal": comparison["oracle_or_second_client_journal_read"] is False,
        "equal_information_baseline_agrees": baseline["equal_information_agrees"],
        "no_false_closure_claim": not comparison["exact_closure_accepted"] and not after["admission_completeness_established"],
    }
    for case in ("primary", "omitted"):
        final = read(root, case + "/retrieve-final-result.json")["record"]
        cancel = read(root, case + "/cancel-confirm-result.json")["record"]
        payments = read(root, case + "/payments-final-result.json")["records"]
        checks[case + "_cancel_verified"] = bool(final["cancelled_at"]) and final["cancelled_at"] == cancel["confirmed_at"] and cancel["order_id"] == final["id"]
        checks[case + "_payment_retained_as_gross_effect"] = len(payments) == 1 and payments[0]["status"] == "succeeded" and payments[0]["amount"] == final["total_amount"]
        checks[case + "_local_cap_retained"] = local[case]["liability_minor"] == int(Decimal(final["total_amount"]) * 100) and local[case]["states"] == ["uncertain"]
    transport = read(root, "transport-counts.json")
    return {"experiment_date_local": "2026-11-01", "timezone": "America/Los_Angeles",
            "checks": checks, "passed": sum(checks.values()), "failed": sum(not c for c in checks.values()),
            "transport": transport, "known_order_reconciliation_passed": known_match,
            "unmanifested_payment_minor": int(Decimal(comparison["observed_unmanifested_payments"][0]["amount"]) * 100),
            "baseline": baseline, "retained_total_minor": sum(v["liability_minor"] for v in local.values()),
            "epoch_completeness_established": False, "independent_observer_established": False,
            "full_provider_impossibility_established": False, "provider_duplicate_request_tested": False,
            "real_network_timeout_observed": False, "provider_price_change_observed": False}


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
