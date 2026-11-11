"""Inspect one proposed stronger snapshot contract against the unchanged gate.

All provider observations are synthetic. Inconsistent observations deliberately
violate the paper's external premises; they are not in-scope counterexamples to
the theorem, real Stripe behavior, or requests available to the untrusted agent.
No network, credentials, provider SDK, or new state-machine model is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.stripe_gate import StripeGate
from trustbound.credential_service import SyntheticProvider, intent


def commands(gate):
    return [list(row) for row in gate.db.execute(
        "SELECT id,payment_id,action,claimed FROM command ORDER BY id")]


def run():
    results = []
    with tempfile.TemporaryDirectory(prefix="trustbound-candidate-") as tmp:
        root = Path(tmp)

        gate = StripeGate(root / "unregistered.db", "epoch")
        try:
            gate.observe(intent("succeeded"))
        except ValueError as exc:
            assert str(exc) == "unknown_payment"
            results.append({"case": "unregistered_observation", "observation_rejected": True})
        else:
            raise AssertionError("unregistered observation unexpectedly accepted")
        gate.close()

        gate = StripeGate(root / "pending.db", "epoch")
        gate.register(intent())
        gate.grant("pi_Boundary1", "capture")
        gate.fence()
        snapshot = gate.snapshot()
        assert not snapshot["known_manifest_resolved"]
        results.append({"case": "fenced_pending_command", "snapshot": snapshot, "commands": commands(gate)})
        gate.close()

        # This is an injected, internally inconsistent trusted observation.
        # Under complete mediation and truthful inert creation, it cannot arise.
        gate = StripeGate(root / "no-command.db", "epoch")
        gate.register(intent())
        gate.fence()
        gate.observe(intent("succeeded"))
        snapshot = gate.snapshot()
        assert snapshot["known_manifest_resolved"] and commands(gate) == []
        assert snapshot["deployment_completeness_proved"] is False
        results.append({"case": "paid_report_without_any_command", "snapshot": snapshot,
                        "commands": [], "out_of_contract_observation": True,
                        "interpretation": "Snapshot summarizes terminal reports, not their admission/dispatch provenance."})
        gate.close()

        # A later contradictory report is rejected, but the cached resolved flag
        # survives. This probes defense against a source-contract failure only.
        gate = StripeGate(root / "contradiction.db", "epoch")
        gate.register(intent())
        gate.fence()
        gate.observe(intent("canceled"))
        try:
            gate.observe(intent("succeeded"))
        except RuntimeError as exc:
            assert str(exc) == "terminal_observation_changed"
        else:
            raise AssertionError("terminal contradiction unexpectedly accepted")
        snapshot = gate.snapshot()
        assert snapshot["known_manifest_resolved"] and snapshot["retained_minor"] == 0
        results.append({"case": "contradiction_after_terminal_report", "contradiction_rejected": True,
                        "subsequent_snapshot": snapshot, "out_of_contract_observation": True,
                        "interpretation": "The snapshot does not carry a persistent contract-violation flag."})
        gate.close()

        # Existing non-deduplicating LOCAL simulator: one synthetic capture,
        # deliberately lost reply, restart, rejected resend, and fresh retrieval.
        path = root / "lost-reply.db"
        provider = SyntheticProvider(root / "provider.db", "TB_BOUNDARY_CANARY_SYNTHETIC")
        gate = StripeGate(path, "epoch")
        gate.register(intent())
        command = gate.grant("pi_Boundary1", "capture")
        gate.fence()

        class LoseReply:
            def request(self, *args):
                provider.request(*args)
                raise TimeoutError("synthetic_lost_reply")

        try:
            gate.dispatch(command, LoseReply())
        except TimeoutError:
            pass
        else:
            raise AssertionError("lost reply was not injected")
        before = gate.snapshot()
        assert not before["known_manifest_resolved"]
        gate.close()
        gate = StripeGate(path, "epoch")
        try:
            gate.dispatch(command, provider)
        except RuntimeError as exc:
            assert str(exc) == "command_unknown_or_already_claimed"
        else:
            raise AssertionError("duplicate dispatch unexpectedly accepted")
        count = provider.db.execute("SELECT COUNT(*) FROM effect").fetchone()[0]
        assert count == 1
        gate.observe(provider.retrieve("pi_Boundary1"))
        after = gate.snapshot()
        assert after["known_manifest_resolved"] and not after["deployment_completeness_proved"]
        results.append({"case": "lost_reply_restart_and_reconcile", "before_reconciliation": before,
                        "after_reconciliation": after, "synthetic_effect_rows": count,
                        "duplicate_dispatch_rejected": True, "commands": commands(gate)})
        gate.close()
        provider.db.close()

    source_paths = ["src/trustbound/stripe_gate.py", "src/trustbound/credential_service.py",
                    "formal/Admission.lean", "formal/StripeGate.lean", "formal/Dispatch.lean",
                    "research/implementation_boundary/check_candidate.py"]
    return {"executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "python_version": platform.python_version(), "sqlite_version": sqlite3.sqlite_version,
            "candidate": "A resolved snapshot independently certifies consistency with durable admission/dispatch history, including detected source-contract failures.",
            "candidate_established": False,
            "cases_executed": len(results), "cases": results,
            "source_sha256": {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths},
            "real_provider_requests": 0, "production_code_changed": False,
            "paper_theorem_refuted": False, "new_formal_proof": False,
            "limit": "Local implementation diagnostics with synthetic provider inputs; not provider conformance, deployment validation, or a novelty result."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"cases_executed": result["cases_executed"],
                      "candidate_established": False, "real_provider_requests": 0,
                      "output": str(args.output)}))
