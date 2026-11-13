"""Execute the real gate against a LOCAL SQLite provider and check trace projections.

The generated Lean terms use only the existing Admission and StripeGate models.
They certify six finite projected histories, not all Python executions or a real
processor. The Python projection and completeness of harness instrumentation are
not proved. Synthetic provider effect commits are distinct from later reads.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from trustbound.stripe_gate import StripeGate
from trustbound.trace_evidence import audit_traces


def initial():
    return {"objects": [], "journal": [], "issued": [], "rights": [],
            "effects": [], "closed": False, "terminal": []}


def advance(state, kind, identity):
    s = deepcopy(state)
    if kind == "allocate":
        s["objects"].insert(0, identity)
    elif kind == "register":
        s["journal"].insert(0, identity)
    elif kind == "dispatch":
        s["issued"].insert(0, identity)
        s["rights"].insert(0, identity)
    elif kind in {"paid", "canceled"}:
        s["terminal"].insert(0, identity)
        s["rights"] = [i for i in s["rights"] if i != identity]
        if kind == "paid":
            s["effects"].insert(0, identity)
    elif kind == "fence":
        s["closed"] = True
    elif kind != "waitOrReject":
        raise ValueError(kind)
    return s


class Harness:
    def __init__(self, directory, name):
        self.name = name
        self.path = directory / (name + "-gate.db")
        self.gate = StripeGate(self.path, "trace-epoch")
        self.provider = sqlite3.connect(directory / (name + "-provider.db"))
        self.provider.executescript("""
        CREATE TABLE objects(seq INTEGER PRIMARY KEY, id TEXT UNIQUE, status TEXT);
        CREATE TABLE events(seq INTEGER PRIMARY KEY, kind TEXT, id TEXT);
        """)
        self.ids, self.steps = {}, []
        self.states = [initial()]
        self.pending_command = None
        self.before_capture = None
        self.lose_reply = False

    def record(self, source_event, identity=None, model_step="waitOrReject"):
        number = self.ids[identity] if identity is not None else None
        state = advance(self.states[-1], model_step, number)
        snapshot = self.gate.snapshot()
        objects = self.provider.execute("SELECT id,status FROM objects ORDER BY seq").fetchall()
        events = self.provider.execute("SELECT kind,id FROM events ORDER BY seq").fetchall()
        # Check projection against actual committed service and simulator rows.
        assert state["objects"] == [self.ids[i] for i, _ in reversed(objects)]
        assert set(state["journal"]) == {self.ids[x["id"]] for x in snapshot["records"]}
        assert len(state["journal"]) == len(snapshot["records"])
        assert set(state["issued"]) == {self.ids[x["payment_id"]] for x in snapshot["commands"]}
        assert state["effects"] == [self.ids[i] for kind, i in reversed(events) if kind == "paid"]
        assert state["terminal"] == [self.ids[i] for kind, i in reversed(events) if kind in {"paid", "canceled"}]
        assert set(state["rights"]) == set(state["issued"]) - set(state["terminal"])
        assert state["closed"] == snapshot["closed"]
        assert not snapshot["has_contract_conflicts"]
        if snapshot["known_manifest_resolved"]:
            assert not state["rights"]
            assert set(state["journal"]) <= set(state["terminal"])
            assert {self.ids[x["id"]] for x in snapshot["records"] if x["status"] == "succeeded"} == set(state["effects"])
        self.states.append(state)
        self.steps.append({"source_event": source_event, "identity": number, "model_step": model_step,
                           "service_snapshot": snapshot, "provider_objects": objects,
                           "provider_events": events, "projected_state": state})

    def allocate(self, identity):
        assert identity not in self.ids
        self.ids[identity] = len(self.ids) + 1
        self.provider.execute("INSERT INTO objects(id,status) VALUES (?, 'requires_payment_method')", (identity,))
        self.provider.commit()
        self.record("provider_allocate", identity, "allocate")

    def retrieve(self, identity):
        status, = self.provider.execute("SELECT status FROM objects WHERE id=?", (identity,)).fetchone()
        return {"id": identity, "object": "payment_intent", "livemode": False,
                "amount": 200, "currency": "usd", "confirmation_method": "manual",
                "capture_method": "manual", "payment_method_types": ["card"],
                "payment_method": None, "customer": None, "status": status,
                "amount_received": 200 if status == "succeeded" else 0,
                "amount_capturable": 200 if status == "requires_capture" else 0}

    def register(self, identity):
        self.gate.register(self.retrieve(identity))
        self.record("service_register_commit", identity, "register")

    def grant(self, identity, action):
        command = self.gate.grant(identity, action)
        # The first durable grant over-approximates remaining payment authority.
        # Further confirm/capture commands for that identity do not issue a
        # second payment right in this one-effect-per-identity model.
        kind = "waitOrReject" if self.ids[identity] in self.states[-1]["issued"] else "dispatch"
        self.record("service_grant_" + action + "_commit", identity, kind)
        return command

    def fence(self):
        self.gate.fence()
        self.record("service_fence_commit", model_step="fence")

    def request(self, method, path, body, idem):
        assert method == "POST" and path.startswith("/v1/payment_intents/")
        identity, action = path.removeprefix("/v1/payment_intents/").split("/")
        assert action in {"confirm", "capture"}
        assert body == ({"payment_method": "pm_card_visa"} if action == "confirm" else {})
        assert idem == "trace-epoch:dispatch:" + str(self.pending_command)
        snapshot = self.gate.snapshot()
        command = next(x for x in snapshot["commands"] if x["id"] == self.pending_command)
        assert command["payment_id"] == identity and command["action"] == action and command["claimed"] == 1
        self.record("claimed_command_at_transport_entry", identity)
        if action == "capture" and self.before_capture is not None:
            callback, self.before_capture = self.before_capture, None
            callback()
        status = self.retrieve(identity)["status"]
        if action == "confirm" and status == "requires_payment_method":
            self.provider.execute("UPDATE objects SET status='requires_capture' WHERE id=?", (identity,))
            self.provider.commit()
            self.record("provider_confirm_commit", identity)
        elif action == "capture" and status == "requires_capture":
            self.provider.execute("UPDATE objects SET status='succeeded' WHERE id=?", (identity,))
            self.provider.execute("INSERT INTO events(kind,id) VALUES ('paid',?)", (identity,))
            self.provider.commit()
            self.record("provider_effect_commit_before_service_observation", identity, "paid")
            if self.lose_reply:
                self.lose_reply = False
                raise TimeoutError("synthetic_lost_reply")
        else:
            self.record("provider_rejected_call", identity)
            return 400, {}
        return 200, self.retrieve(identity)

    def dispatch(self, command, lose_reply=False, before_capture=None):
        self.pending_command = command
        self.lose_reply = lose_reply
        self.before_capture = before_capture
        try:
            self.gate.dispatch(command, self)
        except TimeoutError:
            assert lose_reply
            self.record("service_lost_reply")
        else:
            self.record("service_post_reply_is_not_observation")

    def observe(self, identity):
        self.gate.observe(self.retrieve(identity))
        self.record("service_observation_commit", identity)

    def cancel(self, identity):
        assert self.retrieve(identity)["status"] not in {"succeeded", "canceled"}
        self.provider.execute("UPDATE objects SET status='canceled' WHERE id=?", (identity,))
        self.provider.execute("INSERT INTO events(kind,id) VALUES ('canceled',?)", (identity,))
        self.provider.commit()
        self.record("provider_irreversible_cancel_commit", identity, "canceled")

    def reopen(self):
        self.gate.close()
        self.gate = StripeGate(self.path, "trace-epoch")
        self.record("service_reopen")

    def reject(self, function):
        try:
            function()
        except RuntimeError:
            self.record("service_rejected_operation")
        else:
            raise AssertionError("operation should have been rejected")

    def finish(self):
        snapshot = self.gate.snapshot()
        result = {"name": self.name, "identity_map": self.ids, "steps": self.steps,
                  "states": self.states, "final_snapshot": snapshot,
                  "claims_resolved": snapshot["known_manifest_resolved"]}
        self.gate.close()
        self.provider.close()
        return result


def scenarios(directory):
    traces = []
    p, q = "pi_Trace1", "pi_Trace2"
    h = Harness(directory, "canceled_without_command")
    h.allocate(p); h.register(p); h.fence(); h.cancel(p); h.observe(p)
    traces.append(h.finish())

    h = Harness(directory, "capture_across_fence")
    h.allocate(p); h.register(p)
    confirm, capture = h.grant(p, "confirm"), h.grant(p, "capture")
    h.dispatch(confirm); h.dispatch(capture, before_capture=h.fence); h.observe(p)
    traces.append(h.finish())

    h = Harness(directory, "lost_reply_and_restart")
    h.allocate(p); h.register(p)
    confirm, capture = h.grant(p, "confirm"), h.grant(p, "capture")
    h.dispatch(confirm); h.fence(); h.dispatch(capture, lose_reply=True); h.reopen()
    h.reject(lambda: h.gate.dispatch(capture, h))
    h.reject(lambda: h.gate.grant(p, "confirm"))
    h.observe(p)
    traces.append(h.finish())

    h = Harness(directory, "two_payments_partial_then_complete")
    h.allocate(p); h.register(p); h.allocate(q); h.register(q)
    confirm, capture = h.grant(p, "confirm"), h.grant(p, "capture")
    h.grant(q, "capture"); h.dispatch(confirm); h.fence(); h.dispatch(capture); h.observe(p)
    assert not h.gate.snapshot()["known_manifest_resolved"]
    h.cancel(q); h.observe(q)
    traces.append(h.finish())

    h = Harness(directory, "claim_abandoned_before_send")
    h.allocate(p); h.register(p); command = h.grant(p, "capture"); h.fence()
    h.gate.claim(command); h.record("service_claim_commit_without_invocation", p)
    h.reopen(); h.reject(lambda: h.gate.dispatch(command, h)); h.observe(p)
    assert not h.gate.snapshot()["known_manifest_resolved"]
    traces.append(h.finish())

    h = Harness(directory, "canceled_then_late_dispatch")
    h.allocate(p); h.register(p); command = h.grant(p, "capture"); h.fence()
    h.cancel(p); h.observe(p); h.reject(lambda: h.gate.dispatch(command, h))
    traces.append(h.finish())
    return traces


def lean_state(s):
    core = ', '.join(k + ' := ' + (str(s[k]).lower() if k == 'closed' else str(s[k]))
                     for k in ['journal', 'issued', 'rights', 'effects', 'closed'])
    return '{ objects := ' + str(s['objects']) + ', core := { ' + core + ' }, terminal := ' + str(s['terminal']) + ' }'


def certificate(name, states, steps, resolved, reported):
    out = ["import StripeGate", "open TrustBoundAdmission TrustBoundStripeGate", "namespace " + name]
    for i, state in enumerate(states):
        out.append(f"def s{i} : Provider := {lean_state(state)}")
    guards = {'allocate': 1, 'register': 3, 'dispatch': 4, 'paid': 1, 'canceled': 1, 'fence': 0, 'waitOrReject': 0}
    for i, step in enumerate(steps):
        kind, identity = step['model_step'], step['identity']
        args = f"s{i}" + (f" {identity}" if kind not in {'fence', 'waitOrReject'} else '')
        args += ' (by decide)' * guards[kind]
        out.append(f"theorem step{i} : ApiStep s{i} s{i+1} := ApiStep.{kind} {args}")
    last = f"s{len(steps)}"
    chain = 'ExternalRuns.refl _'
    for i in reversed(range(len(steps))):
        chain = f"ExternalRuns.next step{i} ({chain})"
    out.append(f"theorem recorded_run : ExternalRuns ApiStep start {last} := {chain}")
    out.append("#print axioms recorded_run")
    if resolved:
        out += [f"def reported (id : Nat) : Prop := id ∈ {reported}",
                f"theorem checked_exact {{t : Provider}} (future : ExternalRuns ApiStep {last} t) :",
                f"    (∀ id, id ∈ t.core.effects ↔ id ∈ {last}.core.journal ∧ reported id) ∧ t.core.rights = [] := by",
                f"  apply reconciled_fence_complete (provider_runs_refine recorded_run) (by rfl) reported",
                f"    (by intro id _; simp [{last}])",
                f"    (by intro id _; simp [reported, {last}])",
                "    (provider_runs_refine future)", "#print axioms checked_exact"]
    else:
        out += [f"theorem remains_undrained : {last}.core.rights ≠ [] := by decide", "#print axioms remains_undrained"]
    return '\n\n'.join(out + ['end ' + name, ''])


def main():
    if not __debug__:
        raise SystemExit("Assertions must be enabled; do not use python -O or PYTHONOPTIMIZE.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lean', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    version = subprocess.run([str(args.lean.resolve()), '--version'], capture_output=True,
                             text=True, check=True).stdout.strip()
    if 'version 4.19.0,' not in version:
        raise SystemExit('Use pinned Lean 4.19.0')
    args.output.mkdir(parents=True, exist_ok=False)
    sources = ['src/trustbound/stripe_gate.py', 'src/trustbound/credential_service.py',
               'src/trustbound/trace_evidence.py', 'formal/Admission.lean',
               'formal/StripeGate.lean', 'research/service_refinement/check_traces.py']
    hashes = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}
    with tempfile.TemporaryDirectory(prefix='trustbound-trace-') as tmp:
        traces = scenarios(Path(tmp))
    audit = audit_traces(traces)
    (args.output/'projection-audit.json').write_text(json.dumps(audit, indent=2)+'\n')
    (args.output/'traces.json').write_text(json.dumps(traces, indent=2)+'\n')
    build = args.output/'lean'
    build.mkdir()
    for name in ['Admission', 'StripeGate']:
        (build/(name+'.lean')).write_bytes((ROOT/'formal'/(name+'.lean')).read_bytes())
    env = os.environ.copy()
    env['LEAN_PATH'] = str(build.resolve())
    results = []

    def compile_file(name, accepted, module=False):
        command = [str(args.lean.resolve())]
        if module:
            command += ['-o', name+'.olean']
        command += [name+'.lean']
        result = subprocess.run(command, cwd=build, env=env, capture_output=True, text=True, timeout=90)
        output = result.stdout+result.stderr
        (build/(name+'.log')).write_text(output)
        assert (result.returncode == 0) == accepted, name+'\n'+output
        if accepted:
            assert 'sorryAx' not in output and 'declaration uses \'sorry\'' not in output
        else:
            assert "tactic 'decide' proved that the proposition" in output
            assert 'core.rights' in output and 'is false' in output
        results.append({'name': name, 'expected_accepted': accepted, 'return_code': result.returncode})

    compile_file('Admission', True, True)
    compile_file('StripeGate', True, True)
    for trace in traces:
        paid = [trace['identity_map'][x['id']] for x in trace['final_snapshot']['records'] if x['status'] == 'succeeded']
        name = trace['name']
        (build/(name+'.lean')).write_text(certificate(name, trace['states'], trace['steps'], trace['claims_resolved'], paid))
        compile_file(name, True)
    # Out-of-contract histories corresponding to the two defect probes. These
    # are negative checker inputs, NOT simulated provider executions.
    for name, sequence in [('paid_without_admission', ['allocate','register','fence','paid']),
                           ('paid_after_terminal_cancel', ['allocate','register','dispatch','fence','canceled','paid'])]:
        states, steps = [initial()], []
        for kind in sequence:
            identity = None if kind == 'fence' else 1
            steps.append({'model_step': kind, 'identity': identity})
            states.append(advance(states[-1], kind, identity))
        (build/(name+'.lean')).write_text(certificate(name, states, steps, True, [1]))
        compile_file(name, False)
    summary = {'executed_at_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
               'sqlite': sqlite3.sqlite_version, 'lean': version, 'source_sha256': hashes,
               'executed_service_traces': len(traces), 'projected_steps': sum(len(x['steps']) for x in traces),
               'closed_trace_instances': sum(x['claims_resolved'] for x in traces),
               'unresolved_trace_instances': sum(not x['claims_resolved'] for x in traces),
               'invalid_trace_inputs_rejected': 2, 'compilations': results,
               'checks_passed': True, 'projection_audit_passed': audit['checks_passed'],
               'real_provider_calls': 0, 'universal_implementation_refinement': False,
               'scope': 'Lean checks projected finite execution histories and instantiates existing closure results. Python projection, event capture, SQLite durability, isolation and real-provider semantics remain unproved.'}
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ['executed_service_traces','projected_steps','closed_trace_instances','unresolved_trace_instances','invalid_trace_inputs_rejected','real_provider_calls']}))


if __name__ == '__main__':
    main()
