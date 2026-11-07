"""Read-only inventory of the user's dedicated Duffel test account.

Never use with a shared demonstration account. The auditor reads the primary
manifest and API evidence, not the second client's private journal.
Pagination exhaustion is not an epoch fence.
"""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlencode

from validate_duffel_sandbox import Probe, identifier


def inventory(probe, stage):
    cursor = None
    seen = set()
    records = []
    pages = []
    for page in range(20):
        query = {"limit": 200}
        if cursor:
            query["after"] = cursor
        name = stage + "-page-" + str(page)
        with redirect_stdout(io.StringIO()):
            result = probe.request(name, "GET", "/air/orders?" + urlencode(query))
        if not isinstance(result, list) or any(r.get("live_mode") is not False for r in result):
            raise ValueError("test_inventory_required")
        records.extend({k: r.get(k) for k in ("id", "live_mode", "total_amount", "total_currency", "created_at")} for r in result)
        raw = json.loads((probe.private / (name + "-response.json")).read_text())
        meta = raw.get("meta")
        if not isinstance(meta, dict) or "after" not in meta:
            raise ValueError("pagination_evidence_missing")
        cursor = meta["after"]
        if cursor is not None and (not isinstance(cursor, str) or not cursor):
            raise ValueError("pagination_cursor_invalid")
        pages.append(json.loads((probe.root / (name + "-result.json")).read_text())["request_id"])
        if cursor is None:
            if len({r["id"] for r in records}) != len(records):
                raise ValueError("duplicate_inventory_ids")
            report = {"stage": stage, "records": records, "page_request_ids": pages,
                      "pagination_exhausted": True, "atomic_snapshot_established": False,
                      "admission_completeness_established": False}
            (probe.root / (stage + ".json")).write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps(report, indent=2))
            return report
        if cursor in seen:
            raise ValueError("cursor_cycle")
        seen.add(cursor)
    raise ValueError("inventory_page_limit_no_completeness_claim")


if __name__ == "__main__":
    os.umask(0o077)
    base = Path(os.environ["TRUSTBOUND_DUFFEL_FAILURE_DIR"])
    probe = Probe(base / "audit", Path(os.environ["TRUSTBOUND_DUFFEL_KEY_FILE"]).read_text().strip())
    stage = sys.argv[1]
    if stage in {"inventory-before", "inventory-after"}:
        inventory(probe, stage)
    elif stage == "compare":
        before = json.loads((probe.root / "inventory-before.json").read_text())
        after = json.loads((probe.root / "inventory-after.json").read_text())
        primary = json.loads((base / "primary" / "recover-result.json").read_text())["record"]
        known = {primary["id"]}
        prior = {r["id"] for r in before["records"]}
        current = {r["id"] for r in after["records"]}
        unexpected = sorted(current - prior - known)
        payment_records = []
        for index, oid in enumerate(unexpected):
            identifier(oid, "ord")
            with redirect_stdout(io.StringIO()):
                payments = probe.request("unexpected-payments-" + str(index), "GET",
                                         "/air/payments?" + urlencode({"order_id": oid, "limit": 200}))
            saved = json.loads((probe.root / ("unexpected-payments-" + str(index) + "-result.json")).read_text())
            if saved.get("has_more") is not False:
                raise ValueError("unexpected_payment_listing_incomplete")
            if any(p.get("live_mode") is not False or p.get("order_id") != oid for p in payments):
                raise ValueError("unexpected_payment_binding_mismatch")
            payment_records.extend(saved["records"])
        report = {"primary_manifest_order_ids": sorted(known), "new_unmanifested_order_ids": unexpected,
                  "observed_unmanifested_payments": payment_records,
                  "known_ids_present": known <= current, "exact_closure_accepted": False,
                  "reason": "population_not_fenced; unmanifested activity" if unexpected else "population_not_fenced",
                  "independent_issuer_evidence": False,
                  "oracle_or_second_client_journal_read": False}
        (probe.root / "comparison.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    else:
        raise SystemExit("unsupported_stage")
