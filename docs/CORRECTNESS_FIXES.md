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
