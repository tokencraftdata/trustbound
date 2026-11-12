# Service repairs and checked execution traces

## Reviewer workflow addition

The [reviewer command](../../docs/REVIEWER_GUIDE.md) runs the formal core, selected
service tests, this trace checker, and a separate audit of the exported JSON.
The [audit module](../../src/trustbound/trace_evidence.py) declares each scenario's
expected step count, effects, rights, and closure outcome. It reconstructs the
projection from supplied records and checks command/event deltas, unknown labels,
and final snapshots. Tampering regression tests require inconsistent or incomplete
evidence to fail. The trace checker now refuses Python optimization and enforces
Lean 4.19.0 before running; it writes `projection-audit.json` with the scenario
catalog and event mapping alongside its existing outputs.

These additions do not change the original six scenarios or 66 transitions.
The evidence is finite and supplied by trusted instrumentation; omitted real
routes, universal refinement, and eventual resolution remain unproved. See the
[research contract](../../docs/RESEARCH_CONTRACT.md) for the exact boundary.

## Generated operation schedules

`check_schedules.py` adds 864 deterministic one-payment cases with a separately
maintained oracle. It enumerates grant/fence/dispatch/observe orders, optionally
cancellation, normal/lost-reply/abandoned-claim modes, and reopening after every
action or no restart. A common suffix checks retries and post-fence admission.
The reviewer command includes this checker and records every case outcome.

These are Python tests, separate from the six histories certified by Lean.
They cover bounded serial orderings, not every concurrent or crash execution.
See the [reviewer guide](../../docs/REVIEWER_GUIDE.md#generated-operation-schedules)
for bounds, reproduction, failure replay information, and checker mutation tests.

## Original execution record

Executed 10 November 2026. No real provider requests, new infrastructure,
publication, or repository push. This work strengthens implementation evidence;
it establishes no new general closure principle.

## Repaired behavior

The real SQLite gate now requires a claimed capture command for the same
payment before accepting a positive received amount. A confirm command, an
unclaimed capture command, or another payment's command does not suffice.
A claim is necessary provenance, not proof of invocation or provider execution.

For a known identity, an observation that violates scope, contradicts a terminal
record, or lacks capture provenance writes a persistent conflict before the
method returns its error. The conflict survives reopen and later matching
reports. It blocks resolved status and new grants/claims for that payment.
No automatic clearing operation is provided. Already claimed in-flight work
cannot be withdrawn by this local flag.

Snapshots atomically include payment rows, commands and conflict reasons.
The request-only interface exposes the conflict boolean, not the raw records.
An older database's paid rows are also checked for command provenance before
resolution. A conflicted record retains its configured reservation; that is not
a bound on what a dishonest or out-of-contract processor could charge.

The conflict must commit to survive a crash. Tests kill a worker immediately
before and after that commit: before it, the transaction rolls back; after it,
the conflict remains. This does not prove power-loss durability or truth of an
observation lost before being recorded. Those storage/source contracts remain
explicit.

## What was executed

- **235 local tests passed**, using the existing full dependency environment.
  Of these, **66** exercise the gate, observation checks, request-only interface
  and dispatch crashes; **11** are new observation-integrity regression cases.
  The crash suite covers **15** process-kill points, including conflict commits.
- **Six sequential service executions** produced **66 projected transitions**.
  Lean accepted all six histories under the existing provider-contract model.
  Five final states instantiate the existing exact-closure theorem. The sixth
  has an abandoned claimed command and remains undrained.
- **Two inconsistent trace inputs were rejected** because a paid transition
  lacked an effective right: payment with no grant, and payment after terminal
  cancellation. These are deliberately invalid checker inputs, not processor
  executions, new impossibility results, or an independent mutation benchmark.

[Repair and test report](evidence/REPAIR_REPORT.json) ·
[Trace summary](evidence/summary.json) · [Recorded traces](evidence/traces.json)

The initial full-suite attempt passed 234 tests; the existing socket test was
blocked by the execution sandbox's bind permission. A diagnostic exposed that
specific error, and the entire suite then passed with local socket access. An
earlier attempt in the minimal proof environment lacked broader dependencies.
The report preserves these attempts; no test result has been relabeled as a pass.

## Connection to the existing proof

The harness invokes the actual `StripeGate` implementation and a separate local
SQLite provider simulator. At each recorded step, Python checks the projection
against the committed gate snapshot and simulator rows. This is not a rewritten
Python service or a third abstract transition model.

| Executed action | Projection into the existing provider-contract model |
|---|---|
| Provider creates an inert object | `allocate` |
| Service registers its identity | `register` |
| First durable command grant for that payment | `dispatch`, conservatively representing potential effect authority |
| Additional confirm/capture grant for the same payment | Stutter; command identities are distinct from payment identities |
| Durable admission fence | `fence` |
| Simulator commits a payment effect | `paid`, before the later service observation |
| Simulator irreversibly cancels an object | `canceled` |
| Command claim, confirmation, receipt, read, reopen or rejection | Stutter, retaining any unresolved effect authority |

The six cases cover cancellation without a command, capture admitted before a
fence but committed after it, a lost reply and reopen, two payments that resolve
at different points, a claim abandoned before invocation, and a rejected late
capture after cancellation. This is a chosen finite set, not exhaustive state
exploration or a distribution of production workloads.

Generated Lean terms construct each `ApiStep` with checked guards, compose the
steps into `ExternalRuns`, and instantiate `reconciled_fence_complete` for the
five resolved final states. Those outcome predicates come from the exported
service rows and match the simulator's recorded effect histories in these runs.
Accepted axiom reports use only `propext` and `Quot.sound`. Rejected inputs may
print Lean error-recovery `sorryAx` markers and are never counted as proofs.

**What is proved:** the supplied projected histories are admitted by the existing
model, and its theorem applies to the five specified final states and modeled
continuations. **What remains unproved:** the Python projection, complete event
capture, every implementation execution, SQLite's durability, the credential
boundary, and real-provider terminality/coverage. The trace checks do not
discharge the manuscript's generic implementation-refinement premises.

## Reproduction

Use Python 3.11+ (executed with 3.12.14), pytest 9.0.2 for the tests, and Lean
4.19.0. The trace program itself needs only the Python standard library. It
uses assertions; do not run Python with `-O`. Use a new output directory.

```sh
PYTHONPATH=src python -m pytest -q \
  tests/test_gate_observation_integrity.py tests/test_stripe_gate.py \
  tests/test_dispatch_crashes.py tests/test_credential_service.py
python research/service_refinement/check_traces.py \
  --lean /absolute/path/to/lean-4.19.0/bin/lean \
  --output /tmp/trustbound-service-traces-new
```

The narrow reproduction needs no provider SDK, credentials, Docker or network.
The full repository suite additionally needs its existing optional/project
dependencies and permission to bind a temporary local Unix socket. Running the
tests does not establish OS isolation or real payment-system behavior.
