# Formal models

Lean 4.19.0 with its bundled Std library; Mathlib is not required.

The paper core is `Admission.lean` plus `StripeGate.lean`, checked through
`../scripts/reproduce_core_claim.py`. Its 14 exported results include invariants,
counterexecution statements and a conditional refinement bridge. Eight deliberate
premise-removal mutations must fail to compile. Rejection demonstrates dependence
of the existing proof, not universal assumption minimality.

| Source | Purpose | Scope |
|---|---|---|
| Admission.lean | Fixed journal coverage, fenced drainage and exact identity closure | Empty initial epoch, guarded atomic transitions |
| StripeGate.lean | Inert allocation and guarded activation contract | Model-to-model mapping, not Stripe implementation verification |
| Closure.lean | Amount bounds and observation limits | Separate amount semantics, not composed with the executable gate |
| Observers.lean | Conditional observer/coalition reasoning | Truthful coverage premises are external |
| Dispatch.lean | Durable claim before invocation | Separate single-worker model, not exactly-once provider effects |
| StaggeredClosure.lean | Stable observations at different cuts | Supporting corollary, not novel closure principle |
| ExposureOptimality.lean | Attainable exposure bound in the specified model | No new general least-reservation claim |

The supporting files are included for research provenance. Their theorem counts
must not be summed into a stronger end-to-end claim. The matching `check*.py`
programs describe their own scope; only the selected core is exercised by the
default reproduction command. `check_retention_boundary.py` and
`check_drain_observation.py` are finite diagnostics, not Lean proofs.

The two reviewer examples in `../review/AdmissionSemantics.lean` clarify that
admission cancellation before a first grant is not a permanent tombstone, and
that membership coverage does not require a fence. They are not new core exports.

See [claim boundaries](../docs/CLAIMS.md), [core evidence](../evidence/core/summary.json)
and [current repository validation](../docs/VALIDATION.md).
