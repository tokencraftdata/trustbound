# Framework scope and claims

“Framework” describes the organization of models, code, evidence contracts and
validation tools. It is not an assertion of production maturity or novelty.

## Assumptions

- **A1:** agents are request-only and cannot access the trusted service host,
  credentials, journal or administration.
- **A2:** every effect-capable route in the declared epoch is mediated.
- **A3:** the service records before authority, serializes with the fence and
  does not roll back committed state.
- **A4:** source outcomes are truthful and discharge removes all remaining
  effective rights, including in-flight requests and provider recovery.
- **A5:** exports faithfully include the authoritative journal and outcomes.

These remain real-deployment obligations. A signature, a matching processor
list, a successful test or an isolated database does not independently prove them.

## Supported result

For reachable fenced states in the specified admission model, all future
rights and effects belong to the fixed journal. Once the journaled rights are
discharged and the outcome predicate is truthful, no permitted finite
continuation changes the modeled history, and its effect identities are exactly
those truthfully reported for the journal.

The provider model permits inert object creation before registration, including
after a fence, because activation remains guarded. Unknown objects cannot simply
be declared inert in an actual deployment; exclusive activation is an obligation.

## Important distinctions

- An admission fence does not cancel earlier effective rights.
- Admission-model `cancel` removes current rights; it does not tombstone an
  unissued identity before the fence. The provider model has a separate terminal rule.
- The generic refinement bridge transfers membership coverage only. Concrete
  event multiplicity, ordering, outcomes and amounts need stronger correspondence.
- The empty-start theorem does not import inherited work or prove epoch migration.
- The finite comparator's `coverage_true` means stipulated complete fenced
  evidence, not Lean `Covered`. `assumptions_hold` means no bypass only.
- The 2,048 records are Cartesian assignments, with 64 distinct public inputs
  per arm; the strong comparator is shared code. This is not an independent
  algorithmic baseline or a proof of deployment failure rates.
- Allocation locking, stable-property reasoning and retry handling are not
  claimed as new. The closest-paper comparison establishes no weaker-trust result.

No account-wide payment completeness, independent-issuer certificate, verified
monetary implementation, production booking, legal finality, guaranteed completion
deadline or hostile-host security is established. Separate models do not compose
automatically into one end-to-end theorem.
