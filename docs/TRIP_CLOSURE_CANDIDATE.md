# Trip closure: tested candidate rejected as a new completeness result

**Update, 6 November 2026:** the concrete flight–hotel dependency was checked in
18 finite trace records. It produced an existing stale-authorization failure
and a distinct final business-condition failure, but no exact-closure
composition counterexample. See the [executed check and source comparison](../research/flight_hotel/README.md).
The exploratory assessment below is retained as history, not a claim that its
suggested novelty survived.

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
