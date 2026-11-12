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
