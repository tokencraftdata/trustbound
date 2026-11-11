# Implementation-boundary candidate check — 10 November 2026

**Historical pre-repair screen.** The subsequent repair and its bounded trace
checks are documented in [the service check](../service_refinement/README.md).
The results below bind to their recorded source hashes. To reproduce this
earlier diagnostic, extract `pre_repair_sources.zip` into a separate directory
and run its copy of `check_candidate.py`; its old-behavior assertions are not
expected to pass against the repaired current service.

## Decision

There is a concrete implementation-assurance task worth doing. This check did
**not** establish a new closure principle or a distinguishing result over the
closest papers. The current manuscript and selected release artifact are unchanged.

The candidate examined was stronger than the existing API: could a resolved
snapshot itself certify consistency between the service's durable admissions,
commands and terminal observations, including its handling of a detected source
contract failure? The current API does not offer that certificate. It exposes
`known_manifest_resolved` and explicitly keeps `deployment_completeness_proved`
false. Treating the former as the latter would be an incorrect interpretation.

## Executed checks

The unchanged Python gate was exercised with five small SQLite scenarios. All
provider observations were synthetic. No network, payment account, credential,
new provider, Docker setup, or new formal state machine was used.

| Scenario | Observed behavior | Meaning |
|---|---|---|
| Observation for an unregistered identity | Rejected | Known-object membership is checked. |
| Fence with a pending admitted command | Remains unresolved | The fence is not treated as drainage. |
| Successful-payment report for a registered inert object with no command | Accepted as a resolved known manifest | Terminal reports are not checked against command provenance. This injected history cannot arise under the full stated mediation and truthful-source premises. |
| Canceled report followed by a contradictory successful-payment report | Second report rejected; a subsequent snapshot still says the known manifest is resolved and retains zero | The contradiction is not persisted as a contract-violation flag. This deliberately breaks the source-terminality premise. |
| Synthetic effect followed by lost reply, reopen, duplicate retry and reconciliation | Unresolved until retrieval; duplicate dispatch rejected; one synthetic effect recorded | The existing bounded recovery path behaves as intended. |

These outcomes are in [the execution record](result-2026-11-10.json). The two
inconsistent-observation cases are **not** theorem counterexamples, reachable
traces under all A1–A5, or behavior established for Stripe. Untrusted agents
cannot submit these observations through the restricted command interface.
They identify checks a stronger certificate API would need, rather than a
violation of the current snapshot API's documented meaning.

The existing gate and dispatch-crash suites were also rerun: **30 passed**, with
no failures, errors or skips. This includes the existing process-crash and
two-worker tests, not an exhaustive concurrency or storage proof. See
[the test record](test-summary-2026-11-10.json) and its JUnit file.

Reproduce the focused diagnostic without provider access:

```sh
python research/implementation_boundary/check_candidate.py --output /tmp/trustbound-candidate-new.json
```

The output must not already exist. The program uses assertions; do not run it
with Python optimization enabled. For the existing tests, use the repository's
pinned pytest environment:

```sh
PYTHONPATH=src python -m pytest -q tests/test_stripe_gate.py tests/test_dispatch_crashes.py
```

## Closest-work screen

| Source | What it already establishes or evaluates | Consequence for this candidate |
|---|---|---|
| [EffectBound, V-C and V-D](https://arxiv.org/html/2609.02866v1) | Links authorization to effects with trace checks on its Kafka path; checks finite certificates and malformed evidence under declared coverage assumptions. | Adding a trace checker or a fence/drain certificate is not, by itself, a demonstrated distinction. Its concrete system evidence is stronger than our present payment deployment evidence. |
| [HoldSpec, V-A–V-F](https://arxiv.org/html/2610.14419v1) | Compares its TLA+ and Python state spaces and generates model-based conformance tests, with matched-budget baselines and explicit observability limits. | Model/code consistency checks and generated payment tests are established methods in the closest payment work. Its absence of sandbox credentials does not make a small sandbox run a new general result. |
| [Salas, 6.2 and 7.1](https://arxiv.org/html/2609.31490v1) | Separates mediated effects from bypasses and keeps external-journal completeness and deployment isolation as explicit obligations. | More reconciliation checks cannot establish the absence of all unobserved effects. The proposed work must retain that boundary. |

This focused comparison found no demonstrated separation for the generic
certificate-checking idea. It is not a proof that all future implementation or
payment-specific results are anticipated. The earlier trip and reserve
candidates are not reopened.

## What could actually strengthen the paper

The next useful target is a **justified connection between the existing service
implementation and the checked payment model**. A successful implementation
result would have to cover the admission and fence transactions, command claims,
allowed transport invocations, source observations, and exported decision.
Payment identities and confirm/capture command identities must be related
explicitly: they are not interchangeable objects in the current code and model.

Before claiming that connection:

1. Specify a distinct certification operation, or keep the current API explicitly
   observational. A local resolved flag is not a deployment certificate.
2. Account for contradictory authenticated observations and missing command
   provenance. A stronger certificate should remain unavailable while a known
   contract conflict is unresolved. Merely rejecting one request does not store
   that conflict for later queries.
3. Establish the implementation correspondence. Trace-based testing can find
   mismatches on exercised runs; it is not an all-executions refinement proof.
   Another separately written Lean model would leave the existing gap in place.

Even a proved software core would rely on stated SQLite/storage, adapter,
credential-boundary and processor contracts. It would not prove arbitrary
Stripe behavior or discover effects outside its observation boundary. A1–A2
and the provider part of A4 remain deployment obligations; software verification
can reduce portions of A3 and A5, subject to the concrete correspondence proved.

This is a proposed applied strengthening, not an achieved theorem or a promise
of major novelty. The candidate passes the usefulness test for implementation
assurance, but **does not pass the novelty gate on the evidence available**.
No manuscript claim, release artifact, repository visibility, license or DOI
was changed by this investigation, and nothing was pushed or published.
