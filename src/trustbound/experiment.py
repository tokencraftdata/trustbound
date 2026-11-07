"""Reproducible synthetic comparison using official UCP/AP2 libraries."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from .baselines import Evaluator
from .ledger import AtomicLedger
from .models import BookingFact, ItineraryManifest
from .protocol import ProtocolArtifacts, ProtocolHarness


CONFIGURATIONS = ("ucp_ap2_native", "ap2_plus_parity_policy", "trustbound")
SCENARIOS = (
    "valid",
    "route_mismatch",
    "hotel_date_mismatch",
    "nonrefundable",
    "aggregate_overspend",
    "tampered_mandate",
    "replay",
)


def manifest(index: int) -> ItineraryManifest:
    return ItineraryManifest(
        itinerary_id=f"trip-{index}",
        currency="USD",
        budget_minor=300_000,
        allowed_merchants=("air-alpha", "stay-beta"),
        outbound_origin="SFO",
        outbound_destination="CDG",
        outbound_arrival="2027-06-02T08:00:00Z",
        hotel_city="PAR",
        hotel_checkin="2027-06-02",
        hotel_checkout="2027-06-07",
        return_origin="CDG",
        return_destination="SFO",
        return_departure="2027-06-07T10:00:00Z",
    )


def scenario_fact(m: ItineraryManifest, scenario: str, index: int) -> BookingFact:
    common = dict(
        itinerary_id=m.itinerary_id,
        transaction_id=f"tx-{index}-{scenario}",
        checkout_id=f"checkout-{index}-{scenario}",
        merchant_id="air-alpha",
        merchant_name="Air Alpha",
        item_id="flexible-flight",
        title="Approved flexible travel product",
        amount_minor=100_000,
        currency="USD",
    )
    if scenario == "hotel_date_mismatch":
        return BookingFact(
            **(common | {"merchant_id": "stay-beta", "merchant_name": "Stay Beta", "item_id": "flexible-hotel"}),
            leg="hotel",
            city="PAR",
            start="2027-06-03",
            end="2027-06-07",
        )
    if scenario == "nonrefundable":
        return BookingFact(
            **common,
            leg="flight_out",
            origin="SFO",
            destination="CDG",
            end=m.outbound_arrival,
            refundable=False,
        )
    if scenario == "route_mismatch":
        return BookingFact(
            **common,
            leg="flight_out",
            origin="SFO",
            destination="ORY",
            end=m.outbound_arrival,
        )
    amount = 2_000 if scenario == "aggregate_overspend" else 100_000
    return BookingFact(
        **(common | {"amount_minor": amount}),
        leg="flight_out",
        origin="SFO",
        destination="CDG",
        end=m.outbound_arrival,
    )


def prepare_artifacts(harness: ProtocolHarness, fact: BookingFact, scenario: str) -> ProtocolArtifacts:
    artifacts = harness.issue(fact)
    if scenario == "tampered_mandate":
        final = "A" if artifacts.checkout_mandate[-1] != "A" else "B"
        artifacts = replace(
            artifacts,
            checkout_mandate=artifacts.checkout_mandate[:-1] + final,
            completion_request=copy.deepcopy(artifacts.completion_request),
        )
        artifacts.completion_request["ap2"]["checkout_mandate"] = artifacts.checkout_mandate
    return artifacts


def _percentile(values: list[float], proportion: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(proportion * len(ordered)))]


def run(repetitions: int = 20) -> dict:
    records: list[dict] = []
    for repetition in range(repetitions):
        for scenario_index, scenario in enumerate(SCENARIOS):
            m = manifest(repetition * len(SCENARIOS) + scenario_index)
            harness = ProtocolHarness(m)
            fact = scenario_fact(m, scenario, repetition)
            artifacts = prepare_artifacts(harness, fact, scenario)
            expected = scenario == "valid"
            for configuration in CONFIGURATIONS:
                ledger = AtomicLedger()
                evaluator = Evaluator(configuration, m, harness, ledger)
                if scenario == "aggregate_overspend":
                    seed = ledger.reserve(m.itinerary_id, f"seed-{repetition}-{configuration}", 299_000)
                    assert seed.permitted
                elif scenario == "replay":
                    seed = ledger.reserve(m.itinerary_id, fact.transaction_id, 1)
                    assert seed.permitted
                started = time.perf_counter_ns()
                decision = evaluator.decide(artifacts)
                elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                records.append({
                    "configuration": configuration,
                    "scenario": scenario,
                    "expected_permit": expected,
                    "permitted": decision.permitted,
                    "reason": decision.reason,
                    "latency_ms": elapsed_ms,
                    "has_evidence_commitment": decision.evidence_commitment is not None,
                })
                ledger.close()

    summary: dict[str, dict] = {}
    for configuration in CONFIGURATIONS:
        subset = [row for row in records if row["configuration"] == configuration]
        latencies = [row["latency_ms"] for row in subset]
        summary[configuration] = {
            "attempts": len(subset),
            "false_accepts": sum(row["permitted"] and not row["expected_permit"] for row in subset),
            "false_rejects": sum((not row["permitted"]) and row["expected_permit"] for row in subset),
            "permits": sum(row["permitted"] for row in subset),
            "median_latency_ms": statistics.median(latencies),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "evidence_commitments": sum(row["has_evidence_commitment"] for row in subset),
            "by_scenario": {
                scenario: sum(row["permitted"] for row in subset if row["scenario"] == scenario)
                for scenario in SCENARIOS
            },
        }

    concurrent_ledger = AtomicLedger()
    concurrent_ledger.initialize("concurrency", 5_000)
    with ThreadPoolExecutor(max_workers=20) as pool:
        decisions = list(pool.map(
            lambda i: concurrent_ledger.reserve("concurrency", f"concurrent-{i}", 100),
            range(100),
        ))
    spent, uses = concurrent_ledger.context("concurrency")
    concurrent_ledger.close()
    return {
        "metadata": {
            "repetitions": repetitions,
            "protocol_artifacts_per_scenario": "official AP2 MandateClient SD-JWT/KB-JWT chains inside UCP SDK-validated checkout messages",
            "synthetic": True,
            "ap2_commit": "e1ea56db72a6385bce3e5c1112b3a56ce60acb43",
            "ap2_latest_tag": "v0.2.0",
            "ucp_release": "v2026-08-25",
            "ucp_release_commit": "87dd4b1fcff9105d68173120897237fa784c74ef",
            "ucp_sdk_commit": "eea5af1f7e569fe0fab1d179ed0786be289bef6f",
            "ucp_conformance_commit": "016ecbc22240affdec4429a60d539bedd04ab51b",
        },
        "summary": summary,
        "concurrency": {
            "attempts": 100,
            "permitted": sum(item.permitted for item in decisions),
            "denied": sum(not item.permitted for item in decisions),
            "final_spend_minor": spent,
            "recorded_uses": uses,
            "budget_minor": 5_000,
        },
        "records": records,
    }


def write_results(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    with (output_dir / "attempts.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result["records"][0]))
        writer.writeheader()
        writer.writerows(result["records"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("results"))
    args = parser.parse_args()
    result = run(args.repetitions)
    write_results(result, args.output)
    print(json.dumps({"summary": result["summary"], "concurrency": result["concurrency"]}, indent=2))


if __name__ == "__main__":
    main()

