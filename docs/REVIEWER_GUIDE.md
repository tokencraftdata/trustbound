# Reproduce the reviewer artifact

This workflow checks the formal core, selected service tests, six implementation
histories, their exported evidence, 864 generated operation schedules, 40 scripted agent-behavior cases, and 84 concurrent-worker cases. Start with the
[research contract](RESEARCH_CONTRACT.md) for the contribution, agent role,
terminology, assumptions, and event mapping.

## Setup

Use Linux or macOS, Python 3.11+, and Lean **4.19.0** with its bundled standard
library. Mathlib, provider SDKs, credentials, Docker, and real payment accounts
are unnecessary. The exact Python/SQLite/platform versions are recorded in each
run; testing on one host does not establish a platform compatibility matrix.
Install Lean separately and substitute its absolute binary path below.

From the repository root or the extracted archive root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-reviewer.txt
.venv/bin/python scripts/reproduce_reviewer_artifact.py \
  --lean /absolute/path/to/lean-4.19.0/bin/lean \
  --output results/reviewer-run
```

Use a new output directory. The command checks the pinned Lean version and all
five pinned Python runtime dependencies. Do not set `PYTHONOPTIMIZE` or use `-O`;
the assertion-based checkers now reject that mode explicitly. The standalone
trace-evidence audit uses explicit checks and also works with optimization enabled.

After setup, reproduction makes no network or provider requests. Some selected
tests use child processes and Unix signals to exercise crashes. The larger,
SDK-dependent repository suite remains a separate development check.

## Expected outputs

The repository's `Reviewer artifact` GitHub Actions workflow runs on every push,
pull request, and manual dispatch. Separate Ubuntu 24.04 and macOS 15 Intel workers build
a package from the revision under test, extract it outside the checkout, install
only its pinned dependencies in a fresh environment, and run the command above.
The jobs retain the ZIP, manifest, checksums, summaries, and logs for 30 days.
The full SDK-dependent regression suite runs in a separate Ubuntu job and records
its resolved dependency versions; those broader dependencies are not all pinned.
These jobs test current sources, not the older checked-in release ZIP. A workflow
definition alone is not evidence of a successful run: consult its run status and
downloaded results for the exact revision and platform.

Success means exit status 0 and `checks_passed: true` in `summary.json`:

- `core/`: **14 exported Lean results**, **eight rejected premise-removal
  mutations**, **nine diagnostic tests**, and **2,048 synthetic records**.
- `service-tests.xml`: at least 157 selected gate/interface/crash, observation,
  trace-audit, packaging, and generated-checker tests, all passing with no skips.
  The exact count is recorded in `summary.json`.
- `traces/traces.json`: **six executed histories**, **66 projected transitions**,
  **five closed final states**, and **one undrained final state**.
- `traces/lean/`: generated Lean certificates and compiler logs, including
  **two rejected invalid trace inputs**. These are separate from the eight
  premise-removal mutations in the formal core.
- `traces/projection-audit.json`: each scenario's description, expected outcome,
  and the source-event mapping checked before compilation.
- `exported-trace-audit.json`: a separate replay of the newly written trace JSON.
- `reference-trace-audit.json`: an audit of the included historical example
  traces. These reference traces are not relabeled as new execution evidence.
- `generated-schedules.json`: 864 finite Python cases with replayable operation
  orders, fault modes, restart choices, and final effect/authority counts.
- `agent-behaviors.json`: five scripted request-only policies across four provider
  modes and two restart choices; 40 cases, 12 resolved after the client stops,
  30 after separately labeled operator reconciliation, and 10 still pending.
- `concurrent-clients.json`: 84 threaded-worker cases: 60 resolved, 18 pending,
  and six blocked by a stale-read conflict despite terminal provider outcomes.
  `checks_passed` includes reproduction of this known limitation;
  `conflict_free_concurrent_reconciliation` is **false**.
- `summary.json` and job logs: tool versions, selected source hashes, dependency
  versions, test counts, command results, and explicit evidence limits.

The original four core numbers remain unchanged. The 2,048 diagnostic records
reuse only 64 distinct public inputs per arm; the two strong labels share an
acceptance function. They are not an independent algorithm comparison.

## The six scenarios

1. **Cancellation without a command:** an inert registered object is canceled;
   closure holds with no paid effect and no outstanding right.
2. **Capture across a fence:** authority is granted before fencing and payment
   commits afterward; subsequent observation accounts for one paid identity.
3. **Lost reply and restart:** payment commits, the reply is lost, the service
   reopens and rejects redispatch, and reconciliation recovers the outcome.
4. **Two payments resolving separately:** one payment completes while the other
   remains unresolved; closure becomes possible only after the second is canceled.
5. **Abandoned claim:** a command is durably claimed but never sent. Reopening
   and observing the provider do not discharge its right. The epoch stays open
   for exact closure even though admission has been fenced.
6. **Late dispatch after cancellation:** simulator terminality prevents an
   already-granted capture from producing a new payment.

These are chosen finite cases. The event mapping and assumptions explaining
their authority accounting are in the [research contract](RESEARCH_CONTRACT.md).

## Generated operation schedules

The separate schedule checker enumerates all 24 orderings of grant, fence,
dispatch, and observation, plus all 120 orderings with cancellation added. Each
ordering runs in three modes (normal reply, reply lost after provider commit,
or claim abandoned before send), with and without reopening both SQLite databases
after every action: `(24 + 120) × 3 × 2 = 864` cases.

Each case begins with a registered, confirmed manual-capture payment. A fixed
suffix tests duplicate dispatch, admission after fencing, and final reconciliation.
An independent small state machine predicts allowed operations, outstanding
authority, provider invocations/effects, recorded observations, and closure.
Checks run after each action and reopen. Failures report the operation order,
fault, restart choice, and executed prefix so the case can be replayed.

```sh
.venv/bin/python research/service_refinement/check_schedules.py \
  --output results/generated-schedules.json
```

These are bounded serial orderings of one payment, not all concurrent executions.
Some orders reach the same state. The generated tests simulate lost replies and
abandoned claims; restart here means close/reopen, not a power failure. The existing
subprocess crash tests remain separate. Four deliberately broken gate variants
check sensitivity to a missing fence, repeated claim, premature closure, and
missing journal. The six Lean-certified histories and their proof counts are
unchanged; the 864 cases are Python checks without additional Lean certificates.

## Scripted agent behaviors

The [behavior evaluation](../research/agent_behaviors/README.md) compares a single
attempt, bounded retries, snapshot polling, authoritative reconciliation, and
invalid/replayed requests. All use the actual command service through its limited
request interface. Five policies × four provider modes × two restart choices give
40 deterministic cases. A separate operator reconciliation phase distinguishes
client behavior from later recovery. These are Python checks of scripted clients,
not LLM benchmarks, additional Lean certificates, or a process-isolation proof.

## Concurrent clients and multiple payments

The [concurrency experiment](../research/concurrent_clients/README.md) uses
separate trusted workers and SQLite connections. The bundled socket listener
remains serial. It compares 2/4/8 contending clients over 2/4 payments, forces
cancellation/capture and admission/fence orderings, and delays an older provider
read behind newer evidence. Three repetitions of 28 configurations give 84 cases.
The stale-read cases expose a persistent conservative conflict, not a duplicate
payment. No recovery fix is included; read ordering/versioning remains open.

```sh
.venv/bin/python research/concurrent_clients/evaluate.py \
  --output results/concurrent-clients.json
```

Thread interleavings are not exhaustive or exactly replayable. Recorded event
orders explain observed runs; event barriers reproduce the controlled races.

## Check an exported trace independently of the generator

```sh
.venv/bin/python scripts/check_trace_evidence.py \
  --traces results/reviewer-run/traces/traces.json \
  --output results/reviewer-run/separate-audit.json
```

The output file must be new. This checks consistency of supplied evidence; it
does not run Lean or certify the completeness of a real merchant's records.
Unknown events, missing authority/effects, and unjustified final outcomes are
rejected. Tests also deliberately corrupt traces and require rejection.

## Build and verify a versioned archive

```sh
.venv/bin/python scripts/build_reviewer_artifact.py \
  --output results/TrustBound_Reviewer_Artifact_v1.1.0-review.4.zip
```

The builder uses an explicit source list. It includes Lean sources and checkers,
the selected Python modules and tests, pinned dependencies, documentation, and
recorded reference traces. It excludes credentials, local databases, installed
toolchains, provider probes, and unrelated historical experiments.

It writes a ZIP and a sibling `.sha256` file. Archive entry order, timestamps,
and permissions are fixed, so repeat builds with the same inputs and compression
toolchain are byte-identical. `ARTIFACT_MANIFEST.json` lists every included file
apart from itself and derives a content ID from those hashes. The reviewer
command verifies that manifest before running checks from an extracted archive.
Hashes check integrity relative to the supplied manifest; they are not an
independent signature or attestation of the author.

For macOS, verify and extract the package with:

```sh
shasum -a 256 -c TrustBound_Reviewer_Artifact_v1.1.0-review.4.zip.sha256
unzip TrustBound_Reviewer_Artifact_v1.1.0-review.4.zip -d reviewer-artifact
cd reviewer-artifact
```

On Linux, use `sha256sum -c` for the checksum check. Then follow the setup commands
above in a fresh environment. A successful extracted-package run demonstrates
that the selected package is self-contained; an independent reviewer must still
execute it on their own machine to establish independent reproduction.

## Access and publication

The repository's `paper/release/` directory holds the versioned reviewer candidate
and checksum. Access to that branch or to a separately supplied archive is still
necessary. A private repository link alone does not provide reviewer access.
Public/anonymous distribution and a permanent archive URL or DOI are publication
decisions; generating this package does not make those decisions or grant a
license. Existing terms remain in [RIGHTS_PENDING.txt](../RIGHTS_PENDING.txt).

## Boundaries of the result

A passing run supports conditional abstract proofs and selected implementation
behaviors. It does not establish real-provider coverage, correctness of every
amount, a usable trip, host isolation, universal refinement, or eventual drainage.
The broader protocol/allocation fixes are documented in
[correctness changes](CORRECTNESS_FIXES.md) and tested by the full repository
suite; their SDK-dependent code is outside this selected package. Behavior beyond
the constrained provider contract requires separate mechanisms and evidence.
