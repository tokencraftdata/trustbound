# Concurrent clients and multiple payments

This evaluation extends the serial client-policy comparison with actual threaded
service workers sharing a SQLite journal. Each worker opens its own `StripeGate`
connection and calls the existing `CommandService.handle` interface. The bundled
Unix-socket listener remains serial; this is a test of a possible multiple-worker
arrangement, not evidence that the shipped listener serves requests concurrently.
No production service code, Lean theorem, LLM, or real payment provider is changed
or invoked.

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
- **6 stale-read cases:** one worker reads a nonterminal hotel outcome and pauses
  before applying it. Another worker completes or cancels both payments and
  reconciles them. The older truthful response then arrives behind terminal
  evidence. Fresh reconciliation and database reopening follow.

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
Nineteen regression tests include three broken variants: repeat claims, premature
closure, and a missing journal identity. These are separate from earlier Lean
mutations and checker tests.

## Results and limitation

The reference run meets all scenario assertions: **60 cases resolve, 18 remain
pending, and six remain blocked by a persistent observation conflict**. Every
identity has at most one capture invocation and one paid effect. The overlap
checks observe no premature closure, omitted effect/right, or admission after
the fence. These are results for the recorded cases, not universal guarantees.

The six stale-read cases expose an availability limitation. A truthful older
`requires_capture` response arrives after a newer `succeeded` or `canceled`
observation. `StripeGate.observe` preserves terminal evidence but adds
`terminal_observation_changed`. That conflict persists across fresh reads and
database reopening, keeping `known_manifest_resolved` false although no provider
right remains. The current implementation cannot distinguish this benign read
reordering from contradictory source behavior.

Consequently, **`conflict_free_concurrent_reconciliation` is false**.
`checks_passed: true` means the safety expectations and the explicitly expected
limitation were reproduced. It must not be reported as a clean concurrency result.
No recovery fix is included. Serializing reconciliation or using trustworthy
provider versions needs separate design and validation; simply discarding older
looking responses could hide a genuine provider contract violation.

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
