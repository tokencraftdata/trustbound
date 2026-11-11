# Supplementary run records and travel diagnostic

This repository document holds the detailed material removed from the papers
on 9 November 2026. These are **historical executions**. The manuscript revision
did not rerun Lean, pytest, a simulator, or a provider experiment. A subsequent
final-assurance pass reproduced the selected core; its separate record follows.

For runnable instructions, use [the paper-core guide](../docs/CORE_ARTIFACT.md).
The working repository remains private, and release terms and public artifact
access are pending. This document is not evidence that publication occurred.

## Recorded core runs

On 5 November, the source-isolated run copied eight source and configuration
files and used the existing Lean 4.19.0, Python 3.12.14, and pytest 9.0.2
installations. The packaged artifact was extracted and run with the same tools.
A 6 November repository-export check repeated the core and local simulator;
on 7 November an extracted-core rerun reproduced the same core totals.
These checks made no provider requests and were not clean-machine installations.

## Reading the evidence diagnostic

The saved labels `fenced_reconciliation` and `conventional_reconciliation`
use the stricter rule: reports, fences and contiguous records. `signed_closure`
and `witnessed_log` use the permissive rule. The labels are historical names,
not separately implemented protocols. In particular, no witnessing protocol
is established by the label `witnessed_log`.

`assumptions_hold` means absence of a bypass only; it does not certify A1–A5.
`coverage_true` is the diagnostic's stipulated target, not the Lean `Covered`
invariant. Hidden amounts do not enter grading. The withdrawn 27 October
comparison exposed a hidden-effect flag; the current verifier does not receive
that flag. Equal verdicts for labels using one rule follow by construction.

## Detailed reproduction record

A separate repository-export check on 6 November repeated the selected core
successfully and passed all 40 local simulator assertions, without provider
calls. The broader implementation suite initially passed 221 tests; one local
socket test passed on a focused retry with socket permission and unchanged
source. Thus all 222 cases passed across the two invocations, not in the initial
full-suite run. These implementation tests do not prove A1–A5 or executable
refinement; the nine diagnostic tests are included in the 222, not additional.


A selected-core archive is prepared; public release and reuse terms remain
pending. The private working repository is not public artifact access.

The accompanying minimal artifact contains the two Lean modules, their
checkers, the finite comparator and its nine tests, a reproduction runner,
reference output, and saved evidence. No payment credentials or provider SDK
are required. Use Lean 4.19.0 and Python with pytest 9.0.2; the executed Python
version was 3.12.14. From the artifact root, run:
```sh
python3 \
  scripts/reproduce_core_claim.py \
  --lean /path/to/lean \
  --output results/new-run
```
The output directory must not already exist. The runner copies the selected
inputs, supplies a small environment without payment credentials, disables
automatic pytest plugin loading, and writes command logs, source hashes, JUnit
output and a result summary. Expected totals are 14 exported results, eight
rejected mutations, nine passing tests, 2,048 records, and per-case strong-arm
agreement. No other historical module or full regression suite is silently
included in these counts.

In particular, `checks_passed: true` in `summary.json` reports
successful reproduction for the recorded inputs and tools. It does not report
that a merchant epoch is closed. The journal and source-terminal evidence of a
real deployment are not inputs to this runner.

Packaged logs replace local paths with declared tokens; the original
workspace evidence remains unchanged. A provenance file identifies original
and exported hashes. Hashes detect changes relative to the supplied manifest;
they are not independent witnesses of completeness or authorship. A clean
directory extraction check exercises the packaged files using the existing
toolchains, not an independent environment. Historical provider summaries are
clearly separated from the reproducible core.
Two additional reviewer examples in `review/AdmissionSemantics.lean`
check cancellation before a first grant and membership coverage without a
fence. They were separately compiled while reviewing the manuscript, are not
part of the 14-export count, and establish no new general security claim.


## Flight–hotel candidate check

The toy travel-agent scenario models requests to one trusted payment service.
Hotel capture requires an active flight. Its two failure modes were a commit-time
policy violation and an unusable trip; neither was a payment-completeness failure.

A synthetic flight has already cost 300 units. A hotel capture of 200 is
permitted only while the flight remains active. The model orders hotel
preparation before hotel commit and interleaves flight cancellation; cancellation
has a final refund outcome of 300, 260 or zero units. These are stipulated toy
profiles, not provider contracts. Under stale approval, preparing the hotel,
cancelling the flight, and then capturing the hotel violates the commit policy.
An atomic current-premise guard rejects that capture, matching the shape of
commit-time authorization~([commit-time authorization](https://arxiv.org/pdf/2607.10487v2)). An independent provider would need a
justified enforcement contract for that atomicity; a fresh read alone is
insufficient.

The local checker executed all three event orders, three refund outcomes and
two rules: 18 trace records, 72 prefix records and 120 continuation replays.
Stale approval violates the commit policy in three of nine traces; the atomic
guard violates it in zero of nine. Capturing before cancellation respects that
commit policy but leaves a paid hotel without an active flight. That final
business condition fails in six stale-rule traces and three guarded traces,
while all final payment scopes are closed and their effects reported. Pending
hotel work prevents an earlier full closure claim. No case refutes composition
of exact closure over the common sealed scope. Costs change residual loss, not
this logical distinction.

The checker uses complete observations, atomic toy actions, a fixed population,
and no later admissions. It is a finite diagnostic and a conceptual encoding
comparison, not a new Lean theorem, a reproduced prior implementation, or live
payment evidence. The tested candidate therefore supplies no established new
completeness result. Source and records are in
`research/flight_hotel/`; the existing core proof counts are unchanged.


## Final-assurance reproduction

On 9 November, the selected core was run from the frozen archive after installing
pytest 9.0.2 and its dependencies into a fresh Python virtual environment. It used
the existing Python 3.12.14 runtime and Lean 4.19.0 compiler on the same Mac.
After a documentation-only archive update, an extraction of the final candidate
passed the same checks. Each run accepted 14 exported results, rejected eight
mutations, passed nine tests and regenerated the 2,048 reference records exactly.
There were no provider requests or changes to proof sources, checkers or tests.

This checks Python dependency setup, not a clean machine or a deployment. The
full record is [final assurance](../evidence/final_assurance_2026-11-09/README.md).
The earlier implementation-suite retry remains historical and was not repeated.

## Service repairs and model connection, 10 November

The existing gate now rejects paid observations without an own claimed capture
command and persists known-identity scope, terminality and provenance conflicts.
All 235 local tests passed using the existing full environment and local socket
permission. This total includes 66 selected gate/interface/crash tests and 11 new
observation regression cases. The crash suite now exercises 15 process-kill points.
Earlier dependency and socket-permission failures remain recorded in the
[repair report](../research/service_refinement/evidence/REPAIR_REPORT.json).

Six actual gate histories produced 66 projected model transitions. Lean accepted
all six, checked five closure instances and one undrained final state, and rejected
two deliberately invalid trace inputs. The Python projection and complete event
capture remain trusted. Neither arbitrary implementation traces nor real processor
behavior are proved. No provider requests were made.

The 78-file candidate was extracted and rerun: the original 14/8/9/2,048 core
counts reproduced, all 66 selected service tests passed, and the same trace counts
reproduced. This used the existing tools on the same host. The full implementation
suite is not bundled in the selected archive. [Mapping and commands](../research/service_refinement/README.md).
