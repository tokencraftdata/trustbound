# Correctness changes following review

These are Python implementation changes. The conditional Lean models are unchanged.

## 1. Bind authorization decisions to authenticated data

The protocol verifier now copies the supplied artifacts, authenticates the
checkout, and derives a new immutable `BookingFact` from that signed payload.
The separately supplied fact must match it. Policy checks, budget reservations,
and evidence commitments consume only the returned verified facts and hash.

Verification uses the mandates present in the completion request and requires
them to match the accompanying artifacts. The supported profile has one selected
card instrument and one checkout item; ambiguous instruments or quantities fail
closed. Payment amount, currency, and payee must agree with the signed checkout.
This is the local harness's explicit profile, not generic UCP/AP2 conformance.

Regression tests alter each booking field, substitute completion mandates, add
an extra instrument, disguise a route violation, and try to reserve one unit for
a larger signed purchase. A further test changes caller facts after verification
and checks that the decision still uses the verified snapshot.

## 2. Make allocation retirement safe

Allocation budgets and caps must be nonnegative integers within SQLite's integer
range; booleans, floats, negative values, and invalid lifetimes are rejected before
changing state. The authority's signing identity now survives restart.

A trusted coordinator must call `authority.claim(right, coordinator_id)` before
starting work under a cap. The claim is committed once, atomically with respect
to retirement. Replays and claims of retired, expired, or altered rights fail.
The coordinator remains responsible for enforcing its admitted cap on all work.

Retirement prevents new claims. It releases capacity only if the right was never
claimed. A claimed right keeps its full capacity reserved after retirement,
expiry, restart, or a lost response: it may represent in-flight or already-spent
funds. This prototype offers no automatic settlement/reclamation of claimed caps.
That would require explicit outstanding-work and spent-funds accounting.

**API change:** `verify_allocation(..., authority=authority)` checks current
availability; without a trusted authority it fails closed. It is advisory and
cannot replace the atomic claim. `verify_allocation_signature()` is explicitly
an offline authenticity/time check; signatures remain cryptographically valid
after retirement and must never be used alone as spending permission.

The authority database and its persisted signing key require trusted storage.
Legacy databases without claim history are rejected with a migration error,
rather than guessing whether old tokens can still execute. Tests cover invalid
inputs, restart, tampering, competing claims, and a retirement/claim race.

## 3. Preserve positive payment evidence

An uncertain observation can still contain a positive received amount. The gate
now rejects any later decrease, commits a `received_amount_regressed` conflict,
and leaves the earlier row intact. That conflict survives reopening and blocks
closure even if a later report again looks valid. Matching or increasing amounts
remain observable; terminal-state consistency checks still apply.

The constrained service does not interpret a decrease as a refund: refund and
partial-capture semantics require a different provider contract. Retained capacity
is conservative within the configured scope, not a bound on a dishonest provider.
There is no automatic conflict-clearing operation. The change cannot reconstruct
observations that an older version already discarded. Regression cases cover
partial positive receipts followed by cancellation or lower reports, with and
without a restart before the contradiction.

## 4. Reproduce the artifact on independent CI workers

The reviewer workflow builds and extracts the selected source package on Linux
and macOS, then checks it in a fresh Python environment outside the checkout.
Lean 4.19.0 and the reviewer dependencies are pinned. GitHub Actions references
use full commit hashes. No provider secrets or payment accounts are needed.

Each worker retains its package, manifest, summaries and logs. A separate Linux
job runs the full repository suite, including the protocol and allocation fixes.
CI results establish finite checks on those runner versions, not universal
implementation refinement or a real-provider contract. See the reviewer guide
for how to distinguish a configured job from an observed successful run.

## 5. Generate operation schedules and challenge the checker

The reviewer command now executes 864 cases across all bounded permutations of
grant/fence/dispatch/observe, optionally cancellation, three dispatch fault modes,
and restart after every action or no restart. A separately maintained oracle
checks each operation and durable snapshot, including invocation counts,
outstanding rights, paid effects, retained reservations, and exact observations.
Each case finishes with explicit retry and post-fence admission attempts.

The checker also rejects four intentionally broken implementations: missing
fencing, repeated claims, premature closure, and missing journal records. These
tests assess the checker itself. The full generated case list and outcomes are
included in reproduction output; failed runs preserve a replayable prefix.

These fixes were first packaged in reviewer candidate `1.1.0-review.2`, which
is no longer kept in the repository. The generated cases extend testing but do not change the
Lean theorems or certify concurrent executions, process isolation, real-provider
behavior, or eventual resolution. Close/reopen tests are distinguished from the
existing subprocess crash tests in the reviewer guide.

## 6. Discharge unclaimed commands once a payment is terminal

Review found that `StripeGate.snapshot()` could report `known_manifest_resolved`
while a granted command for a terminal payment was still unclaimed, and that
`claim()` would still accept it. Closure then relied on the provider rejecting
the late request, which is weaker than the Lean premise that no rights remain.

`claim()` now refuses (`payment_terminal`) any command whose payment has been
observed `succeeded` or `canceled`, in the same transaction that records claims.
Once a terminal observation commits, unclaimed authority for that identity can no
longer reach the transport, across restarts. Commands already claimed before the
terminal observation are unchanged: they remain in-flight work governed by the
provider's terminality contract, as before.

The late-capture trace now records one rejected operation instead of a provider
call, so the six projected histories have 64 transitions (previously 66). The
schedule oracle rejects dispatch after a terminal observation, and the
repeat-claim mutant is exercised before observation. A regression test covers
both commands, the absence of any transport call, and reopening the database.
The Lean models are unchanged.

## 7. Release licensing

Code, Lean models, scripts, tests, evidence and technical documentation are
released under the MIT license (`LICENSE`). The manuscript is excluded and will
use arXiv's non-exclusive distribution license (`paper/LICENSE.md`).
`RIGHTS_PENDING.txt` is removed, and the reviewer candidate packages `LICENSE`
in its place.

## 8. Validate direct ledger inputs

`AtomicLedger` now independently requires nonnegative integer budgets and
reservations within SQLite's signed 64-bit range. Booleans, fractional values,
strings, negative values, and overflowing integers are rejected before mutation.
An invalid reservation returns `invalid_amount` and cannot consume a transaction
identity or create capacity. Invalid initialization raises `invalid_budget`.
Zero remains a valid amount. Tests cover restart, identity reuse after rejection,
overspending attempts, and the exact integer boundaries. This fixes the direct
API validation gap; it does not repair historical databases containing invalid
reservations or prove composed approval-to-dispatch monetary correctness.

## 9. Serialize provider retrieval with observation

The command service now calls `StripeGate.reconcile(payment_id, retrieve)`.
A SQLite write transaction covers both the trusted retrieval and validation of
its result, preventing competing service workers from applying a newer read
before an older in-flight read. The returned identity must match the requested
identity. Genuine contradictions still commit durable conflicts; no existing
conflict is cleared or report silently discarded. Direct `observe` remains a
low-level API requiring externally ordered trusted evidence.

The revised 84-case evaluation resolves 66 cases, leaves 18 genuinely pending,
and records no false conflicts. The old six-conflict run is retained as historical
evidence. Tests additionally reject the old unserialized behavior, preserve real
contradictions, and check lock release after retrieval failure and worker death.
The write lock spans the external read, so it can block all journal writers.
Adapters must enforce bounded timeouts and avoid re-entering the journal. Cached
provider responses and historical conflicts remain outside this repair.

## 10. Maintain the evaluation and reviewer workflow

Shared simulator and reporting code lives in `research/support.py`; the serial
schedule and agent evaluators no longer import one another. Their independent
oracles are unchanged. The concurrent simulator remains separate because it has
different state and transaction semantics. The reviewer runner now has named
stages for dependency validation, job execution, output validation, and summary
writing. Failed and timed-out jobs preserve diagnostic logs and exit/timeout
metadata. Reference results are regenerated after these source changes; earlier
versioned archives and the original concurrency findings remain historical.
