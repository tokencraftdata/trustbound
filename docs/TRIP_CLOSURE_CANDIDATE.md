# Research decision: finalize the note; one bounded characterization question

## Current decision — 6 November 2026

Finalize the trusted-service mechanization note independently of new research.
The tested trip-dependency candidate is rejected. Recovery-reserve optimization
is set aside as a diversion from payment completeness. Neither is a trigger for
reviving a trip paper; their earlier screens below are historical.

The only proposed trigger is a genuinely distinguishing characterization of
which semantic coverage and binding conditions permit an auditor to certify
exact closure from per-party evidence. Fix the economic scope, effect identities,
observation interface, admissible continuations and trust assumptions before the
comparison. Authentication alone does not imply truthful or complete assertions.
Shared journals, exclusive mediation and cross-party bindings are possible
realizations, not an exhaustive list of mechanisms proved necessary.

### Bounded investigation and stop rule

Allocate at most two weeks for the primary comparison, with a decision checkpoint
on **20 November 2026** and an absolute stop on **27 November 2026** only if a
specific unresolved comparison justifies the third week. These are research
limits, not a promise of a theorem or unattended work. The **30 November note
target does not depend on this investigation**.

1. Use the existing evidence-rule diagnostic and existing formal statements.
   No travel scenario, new provider, mechanism, infrastructure or third model.
2. Distinguish sound positive certification from deciding true/false in every
   execution, and both from effective finite-time decision. A checker that
   always declines to certify is sound but does not solve the requested problem.
3. Compare a precise proposed necessary-and-sufficient statement with Salas's
   mediation boundary, Zhu and Wang's partition result, and EffectBound's exact
   information states and realizability characterization, as well as their
   cited observation/control foundations. Different payment vocabulary is not
   a separation.
4. **Stop** if the characterization reduces to existing indistinguishability or
   knowledge-of-a-property reasoning, if sufficiency assumes the desired
   completeness fact, or if no distinguishing result survives matched scope
   and assumptions by the limit. Record that outcome and do not revive the trip
   paper on another example. Only a demonstrated difference supports revival.

### Initial screen executed for this revision

Read the existing `certificate_possible_iff` in `formal/Closure.lean`: a sound
positive acceptance at a view exists exactly when every admitted execution
with that view satisfies the chosen predicate. The file explicitly distinguishes
this from computability and finite-time liveness. It also contains a generic
indistinguishable-execution obstruction and preservation by a witness computed
only from the same view. These are already in the repository, outside the
note's selected two-module core; they were not newly proved or rerun here.
Repackaging them would not be a new characterization.

Verified [Salas, sections 4.2 and 6.2](https://arxiv.org/html/2609.31490v1):
reconciliation needs a complete external journal, and detection does not prevent
bypass. Verified [Zhu and Wang, section 7.6](https://arxiv.org/html/2610.00349v1):
the impossibility concerns partition-local spending of a shared unallocated unit
versus global conservation, not an exact-closure auditor. Verified
[EffectBound, section III and Appendix C](https://arxiv.org/html/2609.02866v1):
finite boundary realizability and information-state obstructions already provide
a strong necessary/sufficient comparison target. Different questions alone do
not establish novelty. No structural characterization beyond these results has
been established by this initial screen.

The manuscript now explains why it adopts a trusted-service coverage contract.
The restricted-view bypass diagnostic motivates that choice. The withdrawn
27 October oracle-contaminated experiment is a methodological correction, not
evidence for a general impossibility across independent providers. Expanded
observations and enforceable coverage contracts may remove the ambiguity.

## Earlier candidate assessments (historical)

**Update, 6 November 2026:** the concrete flight–hotel dependency was checked in
18 finite trace records. It produced an existing stale-authorization failure
and a distinct final business-condition failure, but no exact-closure
composition counterexample. See the [executed check and source comparison](../research/flight_hotel/README.md).
The exploratory assessment at the end is retained as history, not a claim that
its suggested novelty survived.

## Recovery-reserve screen — set aside

**Historical decision, superseded above:** the screen proposed further literature
review, but established no new completeness result or research contribution.
The candidate is now set aside; no proof or implementation is authorized by it.

The question is whether small per-provider summaries of outstanding rights,
possible future charges/refunds, and admissible terminal evidence can be composed
to derive the least safe, state-dependent recovery reserve for one flight–hotel
trip. The proposed difference is the derivation and sufficiency of those summaries,
not budgeting, compensation, or the existence of a finite safety game.

For a concrete specification example, take a captured flight of 300 units and a
hotel of 200. A flight refund of 260 is pending; hotel cancellation may charge a
stipulated 20-unit fee. Ask when any capacity may be reused while preserving an
authorized recovery outcome under every contract-permitted continuation. These
are hypothetical contract inputs, not provider facts, an executed experiment, or
a computed minimum. A pending refund is not received money. A cancellation
acknowledgment is not necessarily drainage. The allowed terminal outcome and
required-success worlds must be specified so that rejecting every booking is
not a solution. Unbounded provider uncertainty may preclude guaranteed completion.

### Closest work and the actual remaining difference

| Primary source | Already covered; effect on the candidate |
| --- | --- |
| [Op, sections 7 and 12](https://research.momentum.inc/papers/op.html), unversioned, accessed 2026-11-06 | Least observable allowances for supplied finite demand tables are already covered. Section 12 explicitly leaves state-dependent exposure for reused discharged capacity to a separate construction with conservation and completion proofs. This is a concrete opening in this manuscript, not evidence of an unfilled literature-wide gap. |
| [EffectBound v1, section III and Appendix C](https://arxiv.org/html/2609.02866v1) | Decides finite partially observed safety, truthful claims and required completion. Our inference: bounded balances and trip recovery goals can be encoded in its global state/policy model. Merely doing that is not a new result. A compositional summary construction would need a demonstrable advantage over this matched encoding. |
| [Zhu and Wang, sections 4.7–4.9](https://arxiv.org/html/2610.00349v1) | Compensation has its own authority/accounting, and conservation requires joint component conditions. Holding uncertain exposure and charging compensation do not distinguish TrustBound. |
| [HoldSpec v1](https://arxiv.org/html/2610.14419v1) | Provider-specific hold/terminality models already exist. The inspected one-hold model does not supply the proposed trip reserve construction; adding profiles alone is not a contribution. |
| [Bushehrian, 2017, sections 1–2](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-sen.2016.0180) | Explicitly uses flight–hotel rollback dependencies, paid compensation, and recovery/scheduling optimization. Its mean rollback-cost objective differs from a worst-case, evidence-dependent reserve, but that difference alone does not establish novelty. |
| [Pérez, partial-observation energy games](https://arxiv.org/abs/1512.04255) | Resource safety with hidden state and initial-credit requirements is established quantitative-game territory. This screen inspected the abstract and author-deposited description, not a complete reduction or artifact. Calling money “recovery reserve” does not escape this comparison. |

The apparent opening is therefore **a provider-summary composition construction**,
not a stronger closure guarantee under the same observations. Its outstanding
literature obligation is comparison with compositional quantitative control and
cost-aware transactional-service recovery. This focused search does not establish
that those areas lack the construction.

### Gate before any more proofs

Specify one fixed flight–hotel contract, observations, coupled recovery goal and
resource semantics. Compare a proposed local summary with the full finite product
under identical assumptions and objectives. Establish a concrete distinguishing
property, such as exact reserve computation for a stated class using a provably
smaller sufficient summary. A cheaper reserve than a deliberately conservative
sum, or a hand-written domain instance, is insufficient. If the summaries lose
cross-provider dependencies or existing composition methods already provide the
same construction, stop this candidate.

No new proof, simulation, provider call or infrastructure was executed for this
screen. The earlier 18-trace negative result remains the only trip experiment.
Payment completeness remains an input obligation for releasing capacity; a
recovery reserve does not establish observation completeness or truthful sources.

## Earlier exploratory assessment (historical)

Assessment recorded 6 November 2026. The supplied research report is a proposal
for a separate multi-provider extension; its heading is dated 7 November. That
heading is not evidence of a completed future literature review. Its suggested
theorems and first-result claims have not been proved or adopted by TrustBound.

## The question worth testing

Can a trusted service establish a useful trip-level economic property for a
flight and hotel whose rights are conditional on each other's effects, when
providers have different terminality contracts and compensation can be refused
or incur a fee? This remains a candidate. A travel example, two providers, or a
mechanization alone does not establish a new semantic guarantee.

Before new proofs, define the property and compare it under matched assumptions
with root-scoped quiescence, budget conservation, Op and provider-profile work.
In particular, test whether an effect-conditioned right can already be encoded
as a guarded authority/carrier in the closest model. An encoding would undermine
the claim that economic coupling itself creates a new completeness result.

There is a basic definitional check: if every in-scope effect belongs to one of
a fixed set of providers, and each provider's exact-closure guarantee already
covers all globally permitted continuations, the union of their histories is
stable and accounted for. A counterexample must therefore identify which local
scope, continuation assumption, or additional economic obligation differs. Local
closure and a stronger trip-success or compensation property must not silently
share the same name. This is a logical check, not a new machine-checked theorem.

## Findings checked against primary sources

- [Root-scoped quiescence, sections 2.4 and 5](https://arxiv.org/html/2609.21284v1)
  already distinguishes separate provider snapshots from a consistent composed
  cut and uses adapter barriers and cross-provider channel accounting. A payment
  coupling construction must establish a difference beyond that observation.
- [Budget conservation, sections 4.7–4.8](https://arxiv.org/html/2610.00349v1)
  explicitly treats compensation as a separately authorized, accounted effect
  and discusses mismatched identity/epoch contracts between components. Do not
  claim the first treatment of compensation as a charged effect.
- [AP2 v0.2, Autonomous mode](https://ap2-protocol.org/ap2/specification/#autonomous-human-not-present)
  requires a rejection receipt before subsequent open-mandate presentation and
  explains this as preventing different checkouts using the same open mandate.
  It also leaves agent-to-agent delegation outside its scope. The wording is not
  simply “wait until the previous mandate closes.” A blanket prohibition on
  parallel purchases derived from one high-level user intent is not established
  by this text. Separate authorizations and the scope of “subsequent” require a
  precise protocol interpretation. A documented rule is not itself a novel
  TrustBound theorem or an implemented conformance result.

This is a focused source check, not a completed audit of all report references.
The StAC and broader saga claims, profile-composition gap, and “first mechanized”
priority claim remain to be verified against the original works.

## Planning boundary

The [AAAI-27 Agentic SE site](https://agenticse-aaai.github.io/) lists 20 November
2026, 23:59 AoE. The [CAV 2027 CFP](https://conferences.i-cav.org/2027/cfp/)
lists 20 January 2027, 23:59 AoE, and a 10-page application/case-study category
excluding references and appendices. These dates do not establish readiness,
fit or acceptance. No venue submission has been made.

The November 30 arXiv target remains for the current conditional payment-epoch
case study. The trip-level construction is not a prerequisite or an achieved
replacement contribution. No new provider, infrastructure, theorem or experiment
was added in this diagram revision.
