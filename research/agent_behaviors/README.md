# Scripted agent behavior evaluation

This experiment asks whether different request-generating clients change the
service's payment outcomes and ability to establish closure. It uses the actual
`CommandService.handle` and SQLite `StripeGate`. No LLM, credentials, network,
real payment account, or model API is used. Policies receive only a callback
for serialized requests and responses. This programming interface does not
establish host or process isolation.

## Experimental design

Trusted setup registers and confirms one synthetic 200-cent payment, grants its
capture command, and fences admission. Every client then runs against that same
approved operation. Clients cannot approve, register, fence, cancel provider
work, supply observations, or alter the payment amount through the supported
interface. The permitted operations are dispatch by command ID, public snapshot,
and authoritative reconciliation.

Five deterministic policies receive the same command ID:

- **Single attempt:** dispatch once, inspect stored status once, and stop.
- **Bounded retry:** dispatch, retry at most twice after an error or unsuccessful
  provider status, then inspect stored status. It never reconciles.
- **Snapshot polling:** dispatch once and inspect stored status three times.
- **Reconcile after attempt:** dispatch once, request provider reconciliation,
  then inspect status, whether dispatch returned success or an error.
- **Invalid and replayed requests:** try a forged grant, amount override, forged
  cancellation observation, unknown command, and reopening admission; then
  dispatch the approved command, replay it twice, reconcile, and inspect status.

Each policy runs in four provider modes: a normal response, a lost reply after
payment commit, a captured request that remains pending at the provider, and
irreversible provider cancellation before the client runs. The last is a trusted
scenario setup, not a client cancellation capability. Pending mode records an
invocation without a payment effect and leaves the source nonterminal; it is
distinct from a claim abandoned before send.

Every combination runs both without restart and with close/reopen of both
databases after every request: **5 × 4 × 2 = 40 cases**. Reopening is not process
death or power loss. Cases are serial and contain one payment. The providers
share the constrained schedule simulator's single-effect and terminality rules.

## Measurements and checks

An input-driven oracle predicts each response, command claim, journal entry,
source effect, remaining right, retained amount, and closure verdict. It does
not infer expected values from service snapshots. Checks run after each request
and reopen. Regression tests require rejection of three broken variants:
repeated command claims, premature closure, and acceptance of forged reports.
These are separate from the original eight Lean mutations and four schedule
checker variants.

Each case records the result immediately after the client stops. A separate
trusted operator then requests reconciliation. That action is labeled
`operator` in the transcript and is never credited to the client's policy.
The output retains all requests, replies, gate/provider states, source hashes,
and replay coordinates. A failed run preserves the executed prefix.

## Recorded results

All 40 cases passed. Only the two policies that requested reconciliation
resolved cases themselves: six of eight each, for **12/40** overall. The single
attempt, bounded retry, and snapshot polling policies each resolved zero of
eight. After the separate operator reconciliation, **30/40** were resolved;
all **10** pending-provider cases remained unresolved.

Every policy produced exactly one capture invocation per case and at most one
payment effect. The bounded retry policy submitted 20 approved-command dispatch
requests across its eight cases, versus eight for the single-attempt policy;
both caused eight capture invocations. The invalid-request policy submitted 24
approved-command dispatch requests but caused eight capture invocations. Its 40
out-of-interface or unknown-command probes were rejected. All five policies had
the same payment effects under the same source modes.

These counts describe chosen deterministic programs, not statistical estimates
or a ranking of agent intelligence. The service intentionally requires a fresh
provider retrieval before closing its manifest, so the reconciliation difference
is expected by design. Retrying or polling does not create that evidence.

## Reproduce

From the repository or extracted reviewer archive root, using its Python setup:

```sh
.venv/bin/python research/agent_behaviors/evaluate.py \
  --output results/agent-behaviors.json
```

Use a new output file. The main reviewer command also runs this evaluation and
records its totals in `summary.json`. The checked-in `evidence/results.json`
is a reference execution, not relabeled as a new run during reproduction.
This evaluation adds no Lean certificates and does not establish universal
refinement, concurrent correctness, real-provider contracts, or eventual drainage.
