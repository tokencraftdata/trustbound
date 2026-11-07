"""Finite diagnostic for drain-only evidence, not a new theorem or provider test.

One recorded/issued operation can pay or be irreversibly cancelled. The selected
observer receives the journal, admission fence and a truthful permanent drain
bit, but no past outcome. This is a deliberately weaker hypothetical interface,
not an implemented Stripe endpoint. The model is a finite identity abstraction
of Admission.lean; it is not mechanically refined to that Lean model.
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
    recorded: bool = False
    issued: bool = False
    right: bool = False
    effect: bool = False
    fenced: bool = False


def steps(s):
    if not s.fenced and not s.recorded:
        yield "record", replace(s, recorded=True)
    if not s.fenced and s.recorded and not s.issued:
        yield "grant", replace(s, issued=True, right=True)
    if s.right:
        yield "deliver", replace(s, right=False, effect=True)
        yield "source_cancel", replace(s, right=False)
    if not s.fenced:
        yield "fence", replace(s, fenced=True)


def reachable(start):
    paths = {start: []}
    pending = deque([start])
    while pending:
        s = pending.popleft()
        for action, t in steps(s):
            if t not in paths:
                paths[t] = paths[s] + [action]
                pending.append(t)
    return paths


def view(s):
    # Drain is supplied by the hypothetical truthful source, not inferred from
    # lack of a response or an empty local queue. Effect history is withheld.
    return (s.recorded, s.issued, s.fenced, not s.right)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = reachable(State())
    cuts = [s for s in paths if s.recorded and s.issued and s.fenced and not s.right]
    assert len(cuts) == 2
    witnesses = {}
    for ending in ("deliver", "source_cancel"):
        trace = ["record", "grant", "fence", ending]
        state = State()
        for action in trace:
            state = dict(steps(state))[action]
        witnesses[state] = trace
    assert set(witnesses) == set(cuts)
    worlds = {view(s): [t for t in paths if view(t) == view(s)] for s in cuts}
    assert len(worlds) == 1
    histories = sorted({s.effect for s in cuts})
    assert histories == [False, True]
    pairs = sum(len(reachable(s)) for s in cuts)
    assert all(t.effect == s.effect and not t.right for s in cuts for t in reachable(s))

    # Evaluate all deterministic exact-history outputs for the one shared view.
    # This is semantic grading, not an implementation of any cited paper.
    decisions = []
    for answer in (False, True, None):
        errors = sum(answer is not None and answer != s.effect for s in cuts)
        decisions.append({"answer": answer, "wrong_histories": errors,
                          "sound_on_both": errors == 0})
    assert [x["answer"] for x in decisions if x["sound_on_both"]] == [None]
    # Equal-information conventional reasoning has the identical feasible set.
    baseline_feasible = sorted({s.effect for s in worlds[view(cuts[0])]})
    assert baseline_feasible == histories
    # Positive control: adding truthful past outcome distinguishes the histories.
    enriched = {(view(s), s.effect) for s in cuts}
    assert len(enriched) == 2
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "review_date_local": "2026-11-04",
        "candidate": "exact payment completeness from permanent drain without outcome evidence",
        "candidate_holds_in_diagnostic": False,
        "reachable_states": len(paths),
        "directed_edges": sum(len(list(steps(s))) for s in paths),
        "exploration": "full finite graph, excluding state-preserving self-loops",
        "drained_fenced_cuts": len(cuts),
        "cut_future_pairs": pairs,
        "future_effect_stability": True,
        "shared_view": list(view(cuts[0])),
        "view_fields": ["recorded", "issued", "fenced", "permanently_drained"],
        "indistinguishable_cuts": [{"state": asdict(s), "prefix": witnesses[s]} for s in cuts],
        "possible_past_effects": histories,
        "exact_output_diagnostic": decisions,
        "equal_information_baseline_feasible_effects": baseline_feasible,
        "truthful_outcome_positive_control_classes": len(enriched),
        "full_provider_transcript_equivalence_established": False,
        "novelty_established": False,
        "provider_requests": 0,
        "new_lean_proofs": False,
        "closest_paper_artifacts_executed": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": "Hypothetical restricted snapshot; not an actual API contract, full interactive view, Lean refinement, monetary model, or impossibility for richer evidence.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in (
        "reachable_states", "directed_edges", "drained_fenced_cuts",
        "future_effect_stability", "possible_past_effects", "candidate_holds_in_diagnostic")}))


if __name__ == "__main__":
    main()
