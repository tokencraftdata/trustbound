"""Finite abstract-model audit, NOT a Stripe experiment or a Lean proof.

One authorized request may be dispatched once by a trusted service. A local
fence prevents further dispatch. A processor can temporarily reject that request,
forget the rejection, or permanently seal it. Delivery already in flight does
not revisit the local fence. Exactly one queued delivery is modeled; no retry,
malicious service, credential bypass or duplicate packet is needed for the trace.
"""
import argparse
from collections import deque
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class State:
    sent: bool = False
    queued: bool = False
    local_closed: bool = False
    temporary_rejection: bool = False
    permanent_seal: bool = False
    debits: int = 0


def steps(s):
    if not s.sent and not s.local_closed:
        yield "dispatch_once", replace(s, sent=True, queued=True)
    if not s.local_closed:
        yield "fence_service", replace(s, local_closed=True)
    if s.sent and not s.temporary_rejection:
        yield "install_temporary_rejection", replace(s, temporary_rejection=True)
    if s.temporary_rejection:
        yield "expire_temporary_rejection", replace(s, temporary_rejection=False)
    if s.sent and not s.permanent_seal:
        yield "install_permanent_processor_seal", replace(s, permanent_seal=True)
    if s.queued:
        rejected = s.temporary_rejection or s.permanent_seal
        yield ("deliver_rejected" if rejected else "deliver_effect"), replace(
            s, queued=False, debits=s.debits + (0 if rejected else 1))


def reachable(start):
    paths = {start: []}
    todo = deque([start])
    while todo:
        s = todo.popleft()
        for label, t in steps(s):
            if t not in paths:
                paths[t] = paths[s] + [label]
                todo.append(t)
    return paths


def snapshot(s):
    # The processor's channel is NOT visible to this observer. This is a
    # current snapshot, not a claim of complete interactive-transcript equality.
    return (s.sent, s.local_closed, s.temporary_rejection,
            s.permanent_seal, s.debits)


def follow(s, labels):
    states = [asdict(s)]
    for label in labels:
        s = dict(steps(s))[label]
        states.append(asdict(s))
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = reachable(State())
    graph_edges = sum(len(list(steps(s))) for s in paths)
    # No arbitrary cut-off: exhaust the finite graph, including expiry cycles.
    assert all(0 <= s.debits <= 1 and (not s.queued or s.sent) for s in paths)
    cut = State(sent=True, queued=True, local_closed=True,
                temporary_rejection=True)
    assert cut in paths
    continuation = ["expire_temporary_rejection", "deliver_effect"]
    attack = follow(cut, continuation)
    assert attack[-1]["debits"] == 1 and cut.debits == 0
    assert attack[-1]["local_closed"]

    drained = replace(cut, queued=False)
    assert drained in paths and snapshot(cut) == snapshot(drained)

    sealed_cuts = [s for s in paths if s.local_closed and s.permanent_seal]
    drained_cuts = [s for s in paths if s.local_closed and not s.queued]
    assert sealed_cuts and drained_cuts
    checked_pairs = {}
    for name, cuts in [("permanent_processor_seal", sealed_cuts),
                       ("actually_drained", drained_cuts)]:
        pairs = 0
        for s in cuts:
            futures = reachable(s)
            assert all(t.debits == s.debits for t in futures), (name, s)
            pairs += len(futures)
        checked_pairs[name] = {"cuts": len(cuts), "cut_future_pairs": pairs,
                               "effect_stability": True}

    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": "one authorized dispatch; one queued delivery; finite or permanent processor rejection",
        "reachable_states": len(paths), "directed_edges": graph_edges,
        "exploration": "entire reachable finite state graph, not depth limited",
        "candidate": "local fence plus temporary no-effect protection implies permanent epoch closure",
        "candidate_holds": False,
        "counterexample": {"prefix_actions": paths[cut],
                           "prefix_states": follow(State(), paths[cut]),
                           "continuation_actions": continuation,
                           "continuation_states": attack},
        "snapshot_pair": {"same_snapshot": True, "hidden_delivery_cut": asdict(cut),
                          "drained_cut": asdict(drained),
                          "drained_prefix_actions": paths[drained],
                          "full_transcript_equivalence_proved": False},
        "positive_controls": checked_pairs,
        "current_TrustBound_A4_counterexample": False,
        "current_TrustBound_A4_note": "A4 requires irreversible source discharge; temporary rejection does not satisfy it.",
        "real_provider_requests": 0, "provider_conformance_established": False,
        "Lean_theorem_added": False, "novelty_established": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"reachable_states": len(paths), "directed_edges": graph_edges,
                      "candidate_holds": False, "positive_controls": checked_pairs,
                      "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
