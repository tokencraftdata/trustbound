# Concurrent clients and multiple payments

This evaluation extends the serial client-policy comparison with actual threaded
service workers sharing a SQLite journal. Each worker opens its own `StripeGate`
connection and calls the existing `CommandService.handle` interface. The bundled
Unix-socket listener remains serial; this is a test of a possible multiple-worker
arrangement, not evidence that the shipped listener serves requests concurrently.
The revised command service serializes each provider retrieval with its journal
update. Lean models are unchanged; no LLM or real payment provider is invoked.

## Experimental design

The default run repeats 28 configurations three times, for **84 cases**:

- **54 contention cases:** 2, 4, or 8 clients; 2 or 4 payment identities; normal
  replies, replies lost after commit, or the last payment remaining pending.
  Barriers align the clients' two dispatch attempts per identity. All share the
  same preapproved commands. Final operator reconciliation is separate.
- **12 capture/cancellation cases:** a hotel capture pauses inside transport
  after its durable claim. A flight payment completes; another worker fences,
  attempts a duplicate dispatch, and reconciles while the hotel is pending.
  Cancellation is forced before or after capture commitment, with normal/lost
  replies. A cancellation before capture permits closure only because the source
  contract makes cancellation irreversible, even when the old request resumes.
- **12 admission/fence cases:** independent connections overlap registration or
  a grant with fencing. A test subclass pauses the first transaction immediately
  before commit, while the competing operation starts. Both transaction orders
  are tested. Later registration and grant attempts must be rejected without
  changing the journal. Source objects are canceled and reconciled afterward.
- **6 overlapping-read cases:** one worker reads a pending outcome and pauses.
  An already-claimed capture completes, or the provider cancels the payments,
  while the read is held. A competing reconciler attempts to run. A separate
  zero-wait SQLite connection verifies that the paused read still holds the
  journal write transaction. The competing read proceeds only after release;
  fresh reconciliation and database reopening must establish closure.

Amounts are synthetic 100/200 cents, or 100/200/300/400 cents. The provider uses a
separate SQLite database with atomic, irreversible terminal transitions. It logs
every invocation and has no invocation deduplication or unique effect constraint.
Its transition contract permits at most one payment effect per identity; the
independent invocation check detects repeat sends even if source terminality
would prevent an additional payment. This contract is assumed, not validated
against a real processor.

Each checkpoint compares journal membership, claims, per-identity effects,
remaining authority, observations, retained amounts, and closure with expectations
specified by the scenario. The oracle does not derive those expectations from
the service snapshot. Checkpoints reopen the gate after worker connections close
or while another worker is explicitly paused. This is not a power-loss test.
Twenty concurrency regression tests include four broken variants: repeat claims,
premature closure, a missing journal identity, and an unserialized retrieval.
Six additional reconciliation tests exercise contradictions, identity binding,
retrieval failure, and process termination during retrieval. These are separate from earlier Lean
mutations and checker tests.

## Results and tradeoff

The revised reference run passes all scenario assertions: **66 cases resolve,
18 remain pending, and none has an observation conflict**. Every identity has
at most one capture invocation and one paid effect. The overlap checks observe
no premature closure, omitted effect/right, or admission after the fence.
`conflict_free_concurrent_reconciliation` is true for these bounded cases only.

The earlier run is retained in `evidence/results-before-serialization-2026-11-12.json`:
60 resolved, 18 pending, six false conflicts. That harness let a newer terminal
read overtake a delayed pending read. The revised harness tests the prevented
overtaking with a write-lock probe rather than requiring the old interleaving.
The separate unserialized-read mutation is rejected by that probe.

`StripeGate.reconcile` holds a SQLite write transaction across retrieval and
application. This serializes service reconciliation across workers sharing the
journal. It does not ignore older-looking reports, clear existing conflicts,
or establish ordering for cached or stale provider responses. Direct `observe`
calls still require trusted ordering. Genuine contradictions and mismatched
identities remain durable conflicts. Retrieval exceptions roll back; killing a
worker releases its transaction so another connection can reconcile.

The cost is journal-wide writer blocking during each provider read. Trusted
adapters must use bounded request timeouts and must not re-enter the same journal.
The mechanism does not provide a single atomic snapshot of multiple provider
objects or guarantee eventual progress. These are finite implementation checks,
not a refinement proof.
## Reproduce

From the repository or extracted reviewer archive after the normal Python setup:

```sh
.venv/bin/python research/concurrent_clients/evaluate.py \
  --output results/concurrent-clients.json
```

Use a new output file. `--repeats 1` runs 28 cases for a smoke check; the reviewer
command uses the default three repetitions. The output includes the configuration,
per-case checkpoints, ordered request/reply and provider events, source hashes,
and platform. Failure output retains the executed event prefix. The checked-in
`evidence/results.json` is the reference run, not relabeled as a fresh execution.
Concurrent event orders can differ across reproductions. The event barriers fix
the stated race boundaries, not every OS interleaving. Three repetitions are
neither an exhaustive exploration nor a statistical reliability estimate.

The experiment adds Python evidence only. It does not establish general
linearizability, service-process isolation, real-provider recovery, universal
implementation refinement, general monetary correctness, or eventual drainage.
