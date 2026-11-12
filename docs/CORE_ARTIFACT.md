# TrustBound: selected-core reproducibility artifact

For the current single-command workflow covering this core, selected service
tests, Lean-linked histories, and exported-evidence audits, use the
[reviewer guide](REVIEWER_GUIDE.md). It also describes the versioned archive,
fully pinned test dependencies, and manifest verification. The original narrow
core command and historical evidence remain documented below.

Repository note: the core instructions below describe the narrower 5 November
artifact. The 10 November release candidate adds a separately run service-check
supplement, described at the end; it does not change the original core counts. The repository also contains the broader historical implementation and
provider probes; those are outside the selected-core checks below. See
[the repository README](../README.md) and [fresh validation](VALIDATION.md).

Prepared 5 November 2026 for the manuscript *TrustBound: A Mechanized Case Study
of Payment-Epoch Completeness*. This is a preparation package, not an arXiv
submission or a provider certification. Release licensing is pending; see
RIGHTS_PENDING.txt. No provider account or credentials are needed to run it.

## What a successful run gives you

The goal is a reproducible check of the paper's conditional payment-completeness
model. `summary.json` records `checks_passed: true` only after the selected
checks pass. Inspect the proof and mutation logs, `baseline-tests.xml`, and
`baseline/closure_benchmark.json` alongside it. An expected rejected mutation
is a successful negative check, not a passing proof.

This is a reproduction report, not a certificate that a real merchant epoch
has closed. The runner accepts source files and tools, not a merchant journal
and independently established provider-discharge evidence. A1–A5 and an
implementation-to-model correspondence remain obligations of any deployment.
The current manuscript title is *TrustBound: A Mechanized Note on Payment-Epoch
Completeness*; the older package title below is historical provenance.

## Supported claim

Under the modeled trusted-service rules, record-before-authority and serialized
fencing derive a fixed covered identity population. Truthful per-identity
outcomes and irreversible discharge yield exact closure for all permitted
finite continuations. The source and payment service are trusted. Full mediation
of real actions, source terminality and faithful journal export remain external
obligations. There is no verified monetary composition or new general closure
principle, and no superiority over equal-information reconciliation.

## Reproduce

Install Lean **4.19.0** from its official distribution, and Python with pytest
**9.0.2**. The executed environment uses Python **3.12.14** on Apple Silicon
macOS. Python 3.11+ is the source requirement, not a tested compatibility matrix.
Lean's bundled Std library is sufficient; Mathlib is not required.

Use a Python environment of your choice. A typical setup is:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-core.txt
.venv/bin/python scripts/reproduce_core_claim.py \
  --lean /absolute/path/to/lean-4.19.0/bin/lean \
  --output results/new-run
```

Replace the Lean path. Use a new output directory for every attempt. Do not use
Python's `-O` option, which would disable assertions in the existing checkers.
Dependency downloads require network access during setup; the checks make no
network or payment API requests. The author run reused already installed tools;
the selected archive's dependency installation was tested on this macOS host on
9 November, not across platforms or on an independent clean machine.

Expected outcome: exit 0 and `checks_passed: true` in `results/new-run/summary.json`:

| Check | Expected |
|---|---:|
| Admission exported results | 8 passed |
| Provider-contract exported results | 6 passed |
| Premise-removal proof mutations | 8 rejected |
| Baseline tests | 9 passed; 0 failures/errors/skips |
| Finite comparator records | 2,048 |
| Same-public-evidence groups | 512 |
| Strong comparator verdicts | Equal in every case |

The two strong arms intentionally share the same rule. Their equality is a
consistency check, not evidence of independent product equivalence. The two
weaker arms are mechanism ablations. Bypass cases violate the mediation premise
and expose the information boundary rather than demonstrating successful
bypass detection. Finite counts are not estimated deployment error rates.

Reviewer clarification: the 2,048 records reuse only **64 distinct public inputs**
per arm. Both strong labels share one function, and both weak labels share another;
there is no separate witnessing or signature implementation. `coverage_true`
is the diagnostic's stipulated complete-fenced-evidence predicate, not Lean's
`Covered` membership invariant. Hidden debit amounts are stored but not used to
grade either predicate. Thus this is an evidence-rule diagnostic, not an
independent validation of theorem soundness, monetary coverage or multi-path
composition. Saved result field names and counts are retained for provenance.
The saved `assumptions_hold` flag denotes absence of a bypass only; missing
reports and open fences can still occur. It does not certify all A1–A5.

The abstract admission `cancel` removes existing rights but does not tombstone
an unissued identity: before a fence, a first grant can still follow. The
provider model adds terminal-identity exclusion. The generic real-to-model
bridge transfers membership coverage only; it does not prove preservation of
concrete effect multiplicity, ordering, outcomes or monetary totals.

## Contents and evidence

- `formal/`: Admission.lean, StripeGate.lean and existing checker scripts.
- `src/`, `tests/`: evidence-only comparator and its nine tests. The retained
  package initializer's historical UCP/AP2 description does not imply SDK use;
  no SDK is imported or required by this selected core.
- `scripts/reproduce_core_claim.py`: copies eight inputs and runs selected checks.
- `results/evidence_only_2026-11-01/`: corrected reference result used for exact
  reproduction. The withdrawn 27 October oracle-assisted result is not used.
- `evidence/core/`: exported 5 November execution logs, result summary and JUnit
  evidence. Original commands contain substituted local-path tokens and are
  provenance, not portable commands to paste verbatim.
- `evidence/historical/`: saved non-sensitive reports of the 3 November local
  simulator and real Stripe **test-mode** path. These were not rerun for this
  package. Raw private processor records and provider replay programs are not
  included, so these are reported supporting observations, not independently
  reproduced processor evidence.
- `evidence/CORE_EXPORT_PROVENANCE.json`: original/export hashes and explicit path/hostname redaction records.
- `SHA256SUMS.json`: hashes of every other file in this package.
- `review/`: two separately checked Lean examples clarifying admission
  cancellation and the difference between membership coverage and a fence.
  They are not new core guarantees or part of the original 14-export count.

To check the reviewer examples with Lean 4.19.0 on PATH:

```sh
mkdir -p review/build
lean -o review/build/Admission.olean formal/Admission.lean
LEAN_PATH=review/build lean review/AdmissionSemantics.lean
```

The equivalent commands using an explicit Lean path were executed successfully.
The review also enumerated distinct evidence inputs and checked that all eight
original source/configuration hashes were unchanged. It did not rerun the
original nine-test or eight-mutation suites; their saved execution remains valid
for those byte-identical files.

The historical processor summary reports 21 assertions, nine test HTTP requests,
200 test cents captured, and failed same-user credential/journal isolation.
Complete admission coverage was not established. Its historical full-suite
count of 222 is not part of the fresh selected-core run.

The original core summary contains hashes of **original** logs. For redacted
public logs use evidence/CORE_EXPORT_PROVENANCE.json and SHA256SUMS.json instead; do not interpret the
deliberate path and hostname substitutions as a failed proof or unchanged original log.
Hashes are integrity checks relative to supplied evidence, not independent
attestations. Accepted logs and expected mutation failures are separate.

The distributed source and runner are byte-identical to the selected source
files used in the 5 November core run. An extracted-package check uses existing
toolchains; it does not establish independent clean-machine reproducibility,
real provider coverage, executable-source refinement, or stronger novelty.

## What this package does not exercise

No payment execution, processor SDK, UCP/AP2 conformance, OS isolation, new
provider, network service, deployment credentials, or production booking is
needed. Earlier amount, dispatch, observer and alternative-candidate modules
are intentionally outside this minimal artifact and its reported proof totals.

## Subsequent final assurance

The final 9 November candidate reproduced the same 14/8/9/2,048 totals in a
new Python virtual environment with freshly downloaded pytest 9.0.2 dependencies
and the existing Lean 4.19.0 compiler. The source files and expected result were
unchanged. The archive uses `requirements.txt`; the full working repository uses
`requirements-core.txt`. See [the execution record](../evidence/final_assurance_2026-11-09/README.md).
This remains the same host, not an independent clean-machine reproduction.

## Service-check supplement, 10 November

The current release candidate also contains the repaired SQLite gate, request-only
interface, selected tests and a trace projection checker. From the extracted
78-file candidate, the original core passed again (14 results, eight rejected
mutations, nine tests, 2,048 matching records). A separate 66-test service run
passed. The trace runner reproduced six histories with 66 transitions, five
closure instances, one undrained instance and two rejected invalid inputs.
These runs reused the existing tools on the same host.

```sh
PYTHONPATH=src python -m pytest -q \
  tests/test_gate_observation_integrity.py tests/test_stripe_gate.py \
  tests/test_dispatch_crashes.py tests/test_credential_service.py
python research/service_refinement/check_traces.py \
  --lean /absolute/path/to/lean-4.19.0/bin/lean \
  --output /tmp/trustbound-new-service-check
```

The output directory must be new. The supplement needs no SDK, credentials or
provider requests. The full repository's 235-test suite is broader and requires
its existing optional dependencies and local socket permission. The selected
archive contains only the narrow service tests, not that full suite.

The checker connects finite projected service executions to the existing model.
It does not prove the Python projection, all implementation executions, storage
durability or real-provider behavior. [Exact mapping and evidence](../research/service_refinement/README.md).
