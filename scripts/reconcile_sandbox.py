"""Read-only known-object Stripe observation plus supplied booking comparisons."""
import argparse
import json
import os
from pathlib import Path

from trustbound.reconciliation import compare_records
from trustbound.sandbox_observer import ObservationError, StripeSandboxObserver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--bookings", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--payment-fixture", type=Path)
    mode.add_argument("--stripe-sandbox", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.local.read_text())
    bookings = json.loads(args.bookings.read_text())
    if not isinstance(expected, list) or not isinstance(bookings, list):
        raise SystemExit("Input files must contain JSON arrays")
    failures = []
    if args.stripe_sandbox:
        observer = StripeSandboxObserver(os.environ.get("TRUSTBOUND_STRIPE_TEST_KEY", ""))
        payments = []
        for payment_id in sorted({row["payment_id"] for row in expected}):
            try:
                payments.append(observer.retrieve(payment_id))
            except (ObservationError, ValueError) as exc:
                failures.append({"payment_id": payment_id, "reason": str(exc)})
    else:
        payments = json.loads(args.payment_fixture.read_text())
        if not isinstance(payments, list):
            raise SystemExit("Payment fixture must contain a JSON array")
    report = compare_records(expected, bookings, payments)
    report.update({
        "payment_acquisition": "stripe_sandbox_get" if args.stripe_sandbox else "local_fixture",
        "booking_acquisition": "operator_supplied_unverified_export",
        "observation_failures": failures,
        "payment_observations": payments,
    })
    # Never overwrite input evidence, including via a symlink alias.
    inputs = [args.local, args.bookings] + ([args.payment_fixture] if args.payment_fixture else [])
    if args.output.resolve() in {path.resolve() for path in inputs}:
        raise SystemExit("Output must not overwrite input evidence")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "payment_observations"}, indent=2))
    return 0 if report["records_match"] and not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
