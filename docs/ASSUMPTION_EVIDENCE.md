# From the trust contract to implementation evidence

The current [reviewer workflow](REVIEWER_GUIDE.md) adds an executable audit of
the exported histories, declared scenario outcomes, and tests that corrupt
evidence and require rejection. The [research contract](RESEARCH_CONTRACT.md)
connects those checks to the implementation mechanisms and deployment obligations.
The dated matrix below retains the scope of the original execution evidence.

This matrix accompanies the 10 November manuscript clarification. It identifies
what would justify A1–A5 in a deployment and what the current artifact actually
checks. It adds no experiment, proof, provider contract or infrastructure.

| Premise | Required deployment evidence | Current mechanism and evidence | Remaining obligation |
|---|---|---|---|
| A1: Request-only agents | Enforced separation of caller access from service credentials, journal, code and administration | The request parser accepts dispatch by command ID and status/reconciliation operations. Interface tests reject caller-supplied URLs, amounts and receipts and check reply filtering. | The scope assumes agents cannot access the service machine. Interface checks do not establish host isolation; the historical same-user run did not satisfy A1. |
| A2: Exclusive scoped activation | A fixed-scope inventory of credentials, operators, endpoints, automation and recovery routes; each effect-capable route must be mediated or disabled | Registration precedes grants; the gate fences both. The local harness exposes the modeled paths and records their events. | No real-provider route inventory or exclusive-activation proof is supplied. Signed or matching reports cannot reveal a route omitted from that inventory. |
| A3: Durable ordered service | Atomic ordering of recording, grants and fencing; durable state that cannot roll back; a justified recovery contract for claims and sends | SQLite transactions serialize those gate operations. A claim commits before transport invocation, and claimed commands are not automatically redispatched. Recorded tests exercise 15 process-kill points and a two-worker claim race. | These are selected crash/race tests, not a linearizability or power-loss proof. Storage and trusted transport remain premises. A crash after claim can leave work unresolved indefinitely. |
| A4: Truthful source terminality | Identity-bound truthful outcomes and a provider contract that irreversible discharge excludes all delayed delivery and recovery in scope | The simulator stipulates one effect per identity and irreversible cancellation. Observation checks reject scope/provenance/terminal conflicts and retain committed conflicts. | The simulator contract is not a Stripe contract validation. A claimed command does not prove execution. An authenticated report, a cancellation reply or a timeout alone cannot establish irreversible discharge. |
| A5: Faithful complete export | The entire authoritative journal and truthful outcomes for the same declared scope and cut, with no omitted rows or effects | `snapshot()` reads local payment rows, commands and conflicts in one SQLite transaction. Trace checks compare exported paid identities with the simulator's committed effects. | Sequential processor retrievals are not an atomic processor snapshot. Event capture, the Python projection, source truth and the absence of omitted real routes remain unproved. |

The concrete functions are in [the gate](../src/trustbound/stripe_gate.py) and
[the request interface](../src/trustbound/credential_service.py). Executed
results and their source hashes are in the
[repair report](../research/service_refinement/evidence/REPAIR_REPORT.json).
The six trace checks and their mapping are described in
[the trace guide](../research/service_refinement/README.md).

## What the trace mapping covers

At every recorded step, the checker compares journal membership with payment
rows and issued membership with the payment identities named by command rows.
It compares effects with the simulator's committed payment events, and keeps a
right for each issued identity lacking simulator terminality. A resolved service
verdict additionally requires no remaining rights and matching paid identities.

This explains two important cases. A claim abandoned before invocation retains
its right even when no effect has occurred. A payment committed before a lost
reply remains in the model's effect history even before the service reads it.
Additional confirm/capture commands for one identity are merged only under the
simulator's one-effect-per-identity contract. That merge is not justified for
partial captures, descendants or another provider contract.

Lean checks the generated projected histories and their closure instances.
The instrumented paths, Python projection and complete capture of relevant
events remain trusted. These finite checks do not discharge the generic
all-executions refinement premises or prove eventual resolution.

## Artifact access

The versioned 1.0.0 candidate includes the Lean source, checkers, selected tests,
recorded traces, hashes and reproduction commands. It pins Lean 4.19.0 and
pytest 9.0.2; the executed Python version is recorded as 3.12.14. Its extraction
checks ran on the same host with existing tools. That candidate's access status
is historical. The new versioned reviewer package and checksum are in
`paper/release/`; its sources and builder are on the review branch. The
[reviewer guide](REVIEWER_GUIDE.md) gives the portable command and expected outputs.
Access to a private branch would still require an invitation or separate archive
delivery; packaging alone does not establish public access, a license grant, or
independent execution by a reviewer.
