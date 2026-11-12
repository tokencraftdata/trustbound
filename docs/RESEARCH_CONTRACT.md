# Research contract and evidence boundaries

TrustBound is a focused mechanization note. It brings an explicit payment-service
contract, two checked transition systems, premise-removal checks, and reproducible
local implementation examples together. Mediation, fencing, tracking outstanding
work, and reconciliation are established principles. This artifact does not
establish a new general closure principle or a weaker-trust alternative.

## Terms and running example

An assistant requests a flight and hotel through a payment service. The hotel
payment can outlive the assistant, or complete before its confirmation is lost.
The service needs both a record of past payments and evidence that earlier
permissions cannot produce further payments.

- **Epoch:** a scope of payment operations fixed before admission. The set of
  admitted identities becomes fixed when the service fences admission.
- **Effect:** a modeled payment execution, distinct from sending a request or
  receiving a reply. In this model each identity can produce at most one effect.
- **Outstanding right:** permission that can still produce an effect, including
  work already sent to a provider. An empty client queue does not discharge it.
- **Admission fence:** the ordered operation that blocks new journal entries
  and grants. Previously granted work can remain executable.
- **Discharge:** establishing that a right can no longer produce an effect.
  A timeout, stopped client, or unqualified cancellation reply is insufficient.
- **Identity-level closure:** identifying exactly which operations in the fixed
  journal produced effects and excluding later effects from earlier authority.

For the hotel, “payment ID 1 completed and no old right can charge again” is an
identity-level statement. It does not prove correct prices, currency conversion,
refund accounting, booking authorization at commit time, or a usable reservation.
Those need additional specifications and evidence.

## Why agents appear here

Agents are request-generating software clients. Their intelligence, plans, and
booking quality are not evaluated. The setting illustrates delegated requests
whose lifetime differs from the authority they create. Ordinary asynchronous
applications have the same problem. The executable scenarios exercise the
service and simulator; there is no LLM benchmark or agent-performance result.

## What the formalization contributes

[Admission.lean](../formal/Admission.lean) proves coverage from recording before
granting authority and serialized fencing. After fencing, the journal is fixed
and covers all modeled rights and effects. Discharge prevents later effects;
truthful per-identity outcomes give exact accounting.

[StripeGate.lean](../formal/StripeGate.lean) refines that admission model with a
constrained provider contract: unregistered objects remain inert, activation
requires registration, and terminal objects cannot receive fresh authority.
The name identifies the motivating payment path; the model is not Stripe's
implementation. The one-effect-per-identity contract does not cover partial
captures, descendants, or arbitrary recovery lineages.

The eight premise-removal checks show that particular changes invalidate the
supplied proofs. They do not prove minimal assumptions for a real provider.
The finite comparator shares its strong acceptance rule across two labels;
agreement is a consistency control, not independent algorithmic superiority.

## From assumptions to mechanisms

**A1 — Request-only agents.** The [request service](../src/trustbound/credential_service.py)
accepts only command IDs, snapshot requests, and reconciliation requests. Tests
reject caller-supplied URLs, amounts, and observations and check reply filtering.
A deployment also needs enforced credential, storage, code, and administrative
separation. A Python interface does not provide host isolation.

**A2 — Complete mediation.** The [gate](../src/trustbound/stripe_gate.py) registers
identities before granting commands and serializes admission with its fence.
The trace audit checks that every supplied command and effect is represented.
A deployment still needs an inventory of credentials, operator access, endpoints,
automation, retries, and recovery routes, with each route mediated or disabled.
An omitted route cannot be discovered from evidence that also omits that route.

**A3 — Durable ordering.** SQLite transactions order journal entries, grants,
claims, and fencing. A claim commits before a send; the gate rejects redispatch.
[Crash and concurrency tests](../tests/test_dispatch_crashes.py) exercise 15 kill
points and competing claims. Real storage rollback, replication, power-loss
durability, and an external transport's retry behavior require separate evidence.
An abandoned claim can remain unresolved indefinitely.

**A4 — Irreversible discharge and truthful outcomes.** The local simulator
stipulates one effect per identity and irreversible cancellation. The audit
compares service outcomes with its separately committed event history. Actual
provider contracts must address delayed delivery and recovery, and authoritative
identity-bound observations must justify discharge. Authentication proves origin,
not truth or terminality. Existing defensive service checks are not a proof for
all contradictory or out-of-contract provider responses.

**A5 — Complete, faithful export.** The gate reads its journal, commands, and
conflicts in one transaction. The audit compares every exported row with its
projection and checks that provider events and command claims have matching
source events. A deployment must justify scope, cut consistency, event capture,
and export completeness; sequential provider reads alone are insufficient.

## How implementation events map to the model

The [trace audit](../src/trustbound/trace_evidence.py) contains the executable event
mapping and six scenario expectations. The [harness](../research/service_refinement/check_traces.py)
executes the actual gate against a local SQLite provider simulator.

- Inert provider creation maps to `allocate`; journal registration to `register`.
- The first durable grant for an identity maps to `dispatch`, conservatively
  accounting for authority before a send. Additional confirm/capture commands
  for that identity leave model state unchanged only under the stipulated
  one-effect-per-identity contract.
- Committed fencing maps to `fence`.
- A simulator payment commit maps to `paid` before any service observation.
  Irreversible simulator cancellation maps to `canceled`.
- Claims, intermediate confirmation, reads, lost replies, reopenings, and
  rejected operations leave abstract state unchanged (`waitOrReject`). Their
  concrete command changes are still checked; outstanding rights are retained.

The audit reconstructs membership from the supplied journal, command rows,
provider inventory, and event history. It rejects unknown event labels, missing
or duplicated scenarios, incorrect transitions, omitted authority/effects,
unlogged command changes, rewritten provider histories, and unjustified resolved
flags. This makes the chosen projection inspectable; it does not prove that the
instrumentation captures every possible implementation or provider behavior.

## Interpreting a successful run

Lean establishes conditional properties of the specified models and checks the
generated finite histories. Python tests and exported-evidence audits establish
selected behavior and consistency. They establish neither production readiness,
complete real-provider coverage, universal implementation refinement, nor eventual
resolution. The undrained scenario deliberately demonstrates the last limitation.

See the [reviewer guide](REVIEWER_GUIDE.md) for the single reproduction command,
expected outputs, archive checks, and precise limits of independent reproduction.
