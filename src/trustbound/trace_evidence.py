"""Audit exported LOCAL simulator traces, not a real provider's completeness.

These checks independently reconstruct state from the supplied snapshots and
check event deltas. They cannot detect a route omitted from all supplied evidence.
The projection, instrumentation, storage and provider contracts remain trusted.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


SCENARIOS = {
    "canceled_without_command": {
        "description": "An inert registered object is canceled without any grant.",
        "steps": 5, "effects": 0, "rights": 0, "resolved": True,
    },
    "capture_across_fence": {
        "description": "A previously granted capture commits after admission is fenced.",
        "steps": 12, "effects": 1, "rights": 0, "resolved": True,
    },
    "lost_reply_and_restart": {
        "description": "Payment commits before a lost reply; reopening rejects redispatch and reconciliation finds it.",
        "steps": 15, "effects": 1, "rights": 0, "resolved": True,
    },
    "two_payments_partial_then_complete": {
        "description": "One payment completes while another remains unresolved, then the second is canceled.",
        "steps": 17, "effects": 1, "rights": 0, "resolved": True,
    },
    "claim_abandoned_before_send": {
        "description": "A committed claim is never sent; reopening cannot discharge its outstanding right.",
        "steps": 8, "effects": 0, "rights": 1, "resolved": False,
    },
    "canceled_then_late_dispatch": {
        "description": "After an observed irreversible cancellation, the gate refuses a previously granted late capture without contacting the provider.",
        "steps": 7, "effects": 0, "rights": 0, "resolved": True,
    },
}

EVENT_MAPPING = {
    "provider_allocate": "allocate",
    "service_register_commit": "register",
    "service_grant_confirm_commit": "first_grant_or_stutter",
    "service_grant_capture_commit": "first_grant_or_stutter",
    "service_fence_commit": "fence",
    "provider_effect_commit_before_service_observation": "paid",
    "provider_irreversible_cancel_commit": "canceled",
    "claimed_command_at_transport_entry": "waitOrReject",
    "provider_confirm_commit": "waitOrReject",
    "provider_rejected_call": "waitOrReject",
    "service_lost_reply": "waitOrReject",
    "service_post_reply_is_not_observation": "waitOrReject",
    "service_observation_commit": "waitOrReject",
    "service_reopen": "waitOrReject",
    "service_rejected_operation": "waitOrReject",
    "service_claim_commit_without_invocation": "waitOrReject",
}


class TraceAuditError(ValueError):
    """The supplied trace does not justify its declared projection or outcome."""


def require(condition: bool, message: str) -> None:
    # Deliberately not assert: evidence validation must also work under python -O.
    if not condition:
        raise TraceAuditError(message)


def _initial() -> dict[str, Any]:
    return {"objects": [], "journal": [], "issued": [], "rights": [],
            "effects": [], "closed": False, "terminal": []}


def _successor(previous: dict, kind: str, identity: int | None) -> dict:
    state = deepcopy(previous)
    if kind not in {"fence", "waitOrReject"}:
        require(type(identity) is int and identity > 0, "missing transition identity")
    if kind == "allocate":
        require(identity not in state["objects"], "duplicate allocation")
        state["objects"].insert(0, identity)
    elif kind == "register":
        require(not state["closed"] and identity in state["objects"]
                and identity not in state["journal"], "invalid registration")
        state["journal"].insert(0, identity)
    elif kind == "dispatch":
        require(not state["closed"] and identity in state["journal"]
                and identity not in state["issued"] and identity not in state["terminal"],
                "invalid authority grant")
        state["issued"].insert(0, identity)
        state["rights"].insert(0, identity)
    elif kind in {"paid", "canceled"}:
        require(identity not in state["terminal"], "repeated simulator terminal event")
        require(identity in state["rights" if kind == "paid" else "objects"],
                "effect without authority or cancellation without object")
        state["terminal"].insert(0, identity)
        state["rights"] = [item for item in state["rights"] if item != identity]
        if kind == "paid":
            state["effects"].insert(0, identity)
    elif kind == "fence":
        state["closed"] = True
    else:
        require(kind == "waitOrReject", "unknown model transition")
    return state


def _indexed(rows: list[dict], key: str) -> dict:
    indexed = {row[key]: row for row in rows}
    require(len(indexed) == len(rows), f"duplicate {key} in exported rows")
    return indexed


def _check_projection(step: dict, identities: dict[str, int]) -> None:
    state, snapshot = step["projected_state"], step["service_snapshot"]
    objects = [list(row) for row in step["provider_objects"]]
    events = [list(row) for row in step["provider_events"]]
    records = _indexed(snapshot["records"], "id")
    commands = _indexed(snapshot["commands"], "id")
    object_ids = [row[0] for row in objects]
    require(len(set(object_ids)) == len(object_ids), "duplicate provider object")
    require(set(object_ids) <= identities.keys(), "unmapped provider object")
    require(records.keys() <= set(object_ids), "journal identity absent from provider inventory")
    require(all(row["payment_id"] in records for row in commands.values()),
            "command outside journal")
    require(all(type(row["id"]) is int and row["id"] > 0
                and row["action"] in {"confirm", "capture"}
                and type(row["claimed"]) is int and row["claimed"] in {0, 1}
                for row in commands.values()), "invalid command row")
    require(len({(row["payment_id"], row["action"]) for row in commands.values()})
            == len(commands), "duplicate command authority")
    require(all(kind in {"paid", "canceled"} and identity in object_ids
                for kind, identity in events), "unknown provider event or identity")
    require(len({identity for _, identity in events}) == len(events),
            "multiple terminal effects for one simulator identity")
    terminal = {identity: "succeeded" if kind == "paid" else "canceled"
                for kind, identity in events}
    for identity, status in objects:
        require(status in {"requires_payment_method", "requires_capture", "succeeded", "canceled"},
                "unknown provider status")
        require((status in {"succeeded", "canceled"}) == (identity in terminal),
                "terminal provider object missing its event")
        require(identity not in terminal or terminal[identity] == status,
                "provider status disagrees with effect history")
    require(state["objects"] == [identities[identity] for identity in reversed(object_ids)],
            "object projection mismatch")
    for field, expected in {
        "journal": {identities[identity] for identity in records},
        "issued": {identities[row["payment_id"]] for row in commands.values()},
    }.items():
        require(len(state[field]) == len(set(state[field])) and set(state[field]) == expected,
                f"{field} coverage mismatch")
    require(state["effects"] == [identities[i] for kind, i in reversed(events) if kind == "paid"],
            "effect projection mismatch")
    require(state["terminal"] == [identities[i] for _, i in reversed(events)],
            "terminal projection mismatch")
    require(set(state["rights"]) == set(state["issued"]) - set(state["terminal"]),
            "outstanding authority omitted")
    require(state["closed"] == snapshot["closed"], "fence projection mismatch")
    require(snapshot["has_contract_conflicts"] is False and snapshot["contract_conflicts"] == [],
            "contract conflict cannot certify a selected valid history")
    require(snapshot["deployment_completeness_proved"] is False,
            "trace cannot claim deployment completeness")
    for record in records.values():
        require(record["status"] in {"uncertain", "succeeded", "canceled"}, "unknown service status")
        if record["status"] != "uncertain":
            require(terminal.get(record["id"]) == record["status"], "untruthful terminal report")
    resolved = snapshot["closed"] and all(row["status"] != "uncertain" for row in records.values())
    require(snapshot["known_manifest_resolved"] is resolved, "incorrect resolved flag")
    if resolved:
        require(not state["rights"], "resolved snapshot still has authority")
        reported = {identities[row["id"]] for row in records.values() if row["status"] == "succeeded"}
        require(reported == set(state["effects"]), "resolved snapshot omits a paid identity")


def _check_command_delta(before: list[dict], after: list[dict], event: str,
                         identity: int | None, identities: dict[str, int]) -> None:
    old, new = _indexed(before, "id"), _indexed(after, "id")
    require(old.keys() <= new.keys(), "command disappeared from export")
    added = new.keys() - old.keys()
    is_grant = event in {"service_grant_confirm_commit", "service_grant_capture_commit"}
    require(len(added) == int(is_grant), "command added without its grant event")
    if is_grant:
        command = new[next(iter(added))]
        action = "confirm" if event == "service_grant_confirm_commit" else "capture"
        require(identities[command["payment_id"]] == identity
                and command["action"] == action and command["claimed"] == 0,
                "grant event disagrees with command")
    changed = [key for key in old if old[key] != new[key]]
    is_claim = event in {"claimed_command_at_transport_entry", "service_claim_commit_without_invocation"}
    require(len(changed) == int(is_claim), "command changed without its claim event")
    if is_claim:
        key = changed[0]
        require(old[key]["claimed"] == 0 and new[key] == {**old[key], "claimed": 1}
                and identities[new[key]["payment_id"]] == identity, "invalid claim transition")


def audit_trace(trace: dict) -> dict:
    """Check one recorded history against its declared scenario and event contract."""
    name = trace.get("name")
    require(name in SCENARIOS, "unknown scenario")
    expected = SCENARIOS[name]
    identities = trace["identity_map"]
    require(all(type(value) is int and value > 0 for value in identities.values())
            and len(set(identities.values())) == len(identities), "invalid identity map")
    states, steps = trace["states"], trace["steps"]
    require(len(steps) == expected["steps"] and len(states) == len(steps) + 1,
            "missing or extra recorded step")
    require(states[0] == _initial(), "trace does not start empty")
    previous_commands: list[dict] = []
    previous_events: list[list] = []
    for index, step in enumerate(steps):
        try:
            event, identity = step["source_event"], step["identity"]
            require(event in EVENT_MAPPING, "unmapped source event")
            require(identity is None or identity in identities.values(), "unmapped event identity")
            kind = EVENT_MAPPING[event]
            if kind == "first_grant_or_stutter":
                require(not states[index]["closed"] and identity not in states[index]["terminal"],
                        "grant after fence or terminality")
                kind = "waitOrReject" if identity in states[index]["issued"] else "dispatch"
            require(step["model_step"] == kind, "event mapped to wrong transition")
            following = _successor(states[index], kind, identity)
            require(following == states[index + 1] == step["projected_state"],
                    "state transition mismatch")
            _check_projection(step, identities)
            commands = step["service_snapshot"]["commands"]
            _check_command_delta(previous_commands, commands, event, identity, identities)
            previous_commands = commands
            events = [list(row) for row in step["provider_events"]]
            added = events[len(previous_events):]
            require(events[:len(previous_events)] == previous_events, "provider history rewritten")
            expected_added = []
            if kind in {"paid", "canceled"}:
                source_id = next(key for key, value in identities.items() if value == identity)
                expected_added = [[kind, source_id]]
            require(added == expected_added, "effect or discharge missing its source event")
            previous_events = events
        except (TraceAuditError, KeyError, TypeError, ValueError) as exc:
            raise TraceAuditError(f"{name}, step {index + 1}: {exc}") from exc
    final = trace["final_snapshot"]
    require(final == steps[-1]["service_snapshot"], "final snapshot differs from last recorded cut")
    require(set(states[-1]["objects"]) == set(identities.values()), "unused identity mapping")
    require(trace["claims_resolved"] is expected["resolved"]
            and final["known_manifest_resolved"] is expected["resolved"], "unexpected scenario outcome")
    require(len(states[-1]["rights"]) == expected["rights"]
            and len(states[-1]["effects"]) == expected["effects"], "unexpected final authority or effects")
    return {"name": name, **expected, "checks_passed": True}


def audit_traces(traces: list[dict]) -> dict:
    require(len(traces) == len(SCENARIOS)
            and {trace.get("name") for trace in traces} == set(SCENARIOS),
            "missing or duplicate scenario")
    return {"checks_passed": True, "scenarios": [audit_trace(trace) for trace in traces],
            "event_mapping": EVENT_MAPPING,
            "scope": "Consistency of supplied finite simulator evidence; not complete real-provider coverage or universal refinement."}
