# Flight–hotel candidate: the tested completeness gap does not survive

Executed 6 November 2026. This is a finite, local semantic check against a
precise example plus a source-level comparison. It is not a proof of absence of
all possible trip-level novelty, a new Lean theorem, or reproduction of a cited
implementation. No provider calls or new infrastructure were used.

## One example and three different properties

A flight has been paid for at 300 units. The hotel may capture 200 only while
that flight remains active. A trusted logical service knows all relevant changes.
Hotel preparation precedes hotel commit; flight cancellation can occur before,
between or after them. Cancellation removes the usable flight and finishes with
one of three stipulated refund outcomes: 300, 260, or zero. Refund refusal does
not make the cancelled flight usable. These are toy outcomes, not facts about
Stripe, Adyen, airlines or hotels.

Keep three predicates distinct:

- **Commit authorization:** each hotel capture occurs while the flight is active.
- **Exact payment closure:** all declared payment work is resolved and recorded;
  no permitted continuation adds an in-scope payment effect.
- **Final trip condition:** there is no paid hotel without an active flight.

The last condition deliberately represents one narrow business concern, not
complete trip success. A refund appends a new effect; it does not erase the
historical flight capture. If the hotel right depends only on the *historical
occurrence* of that capture, cancellation never falsifies its condition. The
interesting stale check instead depends on current flight usability.

## Executed checks

Run from the repository root with Python 3.11+ (executed with Python 3.12.14):

```sh
python3 research/flight_hotel/check_example.py --output /tmp/my-trip-check.json
```

Use a new output file. The checker writes with exclusive creation and uses
assertions; do not run with `-O`. Saved output is [result.json](result.json).

| Local rule | Trace records | Commit-policy violations | Final trip-condition failures |
|---|---:|---:|---:|
| Use approval-time snapshot | 9 | 3 | 6 |
| Check current condition atomically with capture | 9 | 0 | 3 |

There are three orderings, three refund outcomes and two rules: **18 records**,
**72 prefix records**, and **120 continuation replays**. These reuse states;
they are exhaustive for this tiny declared schedule, not independent samples.
The checker found **zero counterexamples to composition of exact payment
closure** within the sealed scope and rejected the premature hotel-closure claim.

The violating order is prepare hotel → cancel flight → capture hotel. With a
40-unit retained flight fee, stale approval yields 240 net units spent; the
atomic guard rejects the hotel capture and leaves 40. Refusing the flight refund
instead leaves 500 versus 300. These numbers illustrate loss, not new conservation
results. If hotel capture precedes cancellation, both rules authorize it at that
time; the final trip condition can subsequently fail while both payment histories
are completely accounted for. Calling that a failure of *payment completeness*
would change the property being tested.

## Closest-work comparison

| Source and inspected location | Encoding of this example / resulting boundary |
|---|---|
| [EffectBound v1, II-A–B, III and Appendix C](https://arxiv.org/html/2609.02866v1) | Hotel authority becomes an instance carried to the capture frontier; the flight condition belongs to the application policy over histories. Its framework already admits policy-rejected continuations. A new travel label does not establish a new closure principle. |
| [Commit-time authorization v2, 3 and 4.2–4.3](https://arxiv.org/pdf/2607.10487v2) | Flight usability is a required current premise of the exact hotel effect. The atomic guard is a direct conceptual instance. Cross-service derived grants have weaker revocation behavior; we do not claim a remote read implements the atomic premise. |
| [Salas v1, 3.2, 6.2 and 7](https://arxiv.org/html/2609.31490v1) | Known governing dependencies are checked at authoritative admission, and bypass completeness remains external. Its admitted outbox decision survives later amendment; it is not identical to our sink-time guard. The difference is already explicit in its contract, rather than a discovered violation. |
| [AcquireBound v2, 4.5, 5.6–5.7](https://arxiv.org/html/2609.14744v2) | Quarantine is distinct from authority, registered state preconditions are checked at effect commit, and verified destruction fences dependent descendants. Refund alone does not prove capability removal. Merely adding a dependency edge is insufficient to distinguish our candidate. |
| [Root-scoped quiescence v1, 2.4 and 5](https://arxiv.org/html/2609.21284v1) | Handoffs and earlier work remain in the shared-cut accounting. A hotel right still able to execute defeats full closure; a local object-status snapshot cannot hide it legitimately. |
| [Budget conservation v1, 4.7–4.8](https://arxiv.org/html/2610.00349v1) and [Op, 3.1 and 4](https://research.momentum.inc/papers/op.html) | Further authorized effects and scoped compensation already preserve the distinction between historical payment and restoration of a business condition. We have not established a new fee-bearing compensation theorem. Op is unversioned; accessed 6 November 2026. |

These mappings are conceptual comparisons, not machine-checked refinements into
those authors' models. The checker implements our two minimal rules; it does not
execute their artifacts or measure their performance.

## Decision and remaining boundary

**Reject this example as the headline of a novel trip-completeness paper.** The
stale capture is an existing current-premise problem; the later unusable trip is
a business-condition problem; premature closure omits outstanding authority.

The model assumes truthful complete observations, atomic service/sink checking,
a fixed provider population, and no new admissions after the declared work.
All possible flight changes are mediated here. A real airline changing flight
status independently would require a different enforcement/observation contract;
this experiment neither implements it nor establishes a new impossibility.
There is no new completeness theorem ready to promise in a trip-paper introduction.
Retain the corrected mechanization note and do not expand this candidate into
infrastructure or a broader provider experiment.
