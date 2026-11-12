# Artifact release candidates

## Reviewer candidate 1.1.0-review.3

The current [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.3.zip) and
[checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.3.zip.sha256) contain 39
entries, including the manifest. This version adds the
[scripted-client evaluation](../../research/agent_behaviors/README.md), its
regression checks, and a labeled reference execution. The five policies run
through the actual restricted command service in 40 deterministic cases.

The archive was extracted outside the checkout and the complete reviewer command
passed using the existing pinned Python 3.12.14 reviewer environment and Lean
4.19.0. It reproduced the unchanged 14/8/9/2,048 core totals, six histories with
66 transitions, and 864 operation schedules. All 138 selected tests passed.
The broader repository suite separately passed 355 tests. In the 40 new cases,
12 resolved after client actions and 30 after separately labeled operator
reconciliation; all 10 pending-provider cases stayed unresolved. No case produced
more than one capture invocation or payment effect.

The [verification record](reviewer-verification-v1.1.0-review.3.json) binds the
run to this archive and records an earlier interrupted attempt: the outer
180-second command limit expired during the schedule sweep. A complete rerun
with a longer limit passed; the interrupted attempt is not counted as success.
This local reproduction reused an existing environment and is not evidence of
an independent review. Source revision: `aa828267859186abe77d1e15ee18cd6124190177`.

[CI run 43293947080](https://github.com/tokencraftdata/trustbound/actions/runs/43293947080)
also passed on separate Ubuntu 24.04 and macOS 15 Intel workers. Both reproduced
the same content ID and all new client outcomes. The
[retained summaries](ci-run-43293947080/run.json) and full-suite JUnit record bind
these results to `aa82826`; they are separate from the local verification record.

The archive can be handed directly to a reviewer and used without a repository
account after dependency setup. It is separate from the manuscript source ZIP.
An anonymous/public mirror, permanent DOI, and release terms remain pending.
The earlier packages remain unchanged. These client policies are scripted
programs, not LLM evaluations, new Lean proofs, or production certification.

## Historical reviewer candidate 1.1.0-review.2

The historical [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.2.zip) and
[SHA-256 checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.2.zip.sha256) contain
35 entries, including the manifest. This version adds the positive-receipt fix,
864 generated operation schedules, checker mutation tests, and updated guidance.
The protocol and allocation fixes remain in the broader SDK-dependent repository
suite, outside this selected package.

The extracted ZIP passed the [reviewer command](../../docs/REVIEWER_GUIDE.md) in
a new Python 3.12.14 environment on the same Apple Silicon Mac. It reproduced
the unchanged 14/8/9/2,048 formal/diagnostic totals and the six Lean-certified
histories, with 123 selected tests passing. All 864 generated cases passed;
768 resolved and 96 correctly retained outstanding authority. The full
repository suite separately passed 340 tests. Dependencies were freshly
installed into the new environment using pip's cached pinned wheels; the Lean
installation was reused.

The [verification record](reviewer-verification-v1.1.0-review.2.json) binds these
results to this archive's hash and content ID. GitHub's `Reviewer artifact`
workflow additionally builds each tested revision on independent Linux and
macOS workers; inspect the corresponding run's status and downloadable results.
The local record above is not itself independent-machine evidence. The generated
cases are bounded Python checks, not new Lean proofs or deployment certification.

The earlier archives remain unchanged. Access and licensing limitations below
continue to apply; creating this candidate does not publish a DOI or grant a license.

## Historical reviewer candidate 1.1.0-review.1

The [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.1.zip) and
[SHA-256 checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.1.zip.sha256) package
the formal core, selected service code and tests, explicit trace audit, recorded
reference histories, and the fully pinned reviewer dependencies. The archive has
32 entries, including its manifest. Its builder is
[`scripts/build_reviewer_artifact.py`](../../scripts/build_reviewer_artifact.py).

The archive was extracted and the [single reviewer command](../../docs/REVIEWER_GUIDE.md)
passed in a new virtual environment with freshly downloaded dependencies on the
same Apple Silicon Mac and the existing Lean 4.19.0 installation. The original
14/8/9/2,048 core totals reproduced, 93 selected tests passed, and six histories
with 66 transitions passed both the Lean checks and exported-evidence audit.
Five final states were closed, one remained undrained, and two invalid Lean trace
inputs were rejected. The broader repository suite passed 262 tests separately.

[Verification record](reviewer-verification.json) records the tested archive hash,
content ID, tool versions, and result counts. This is a fresh Python environment
on the same host, not an independent review or cross-platform execution.

This candidate is available through this repository branch or separate archive
delivery. It is not a DOI deposit or a new license grant. Reviewer access still
depends on access to the branch or supplied ZIP; publication and anonymous access
must be arranged separately if that access is restricted.

## Historical 1.0.0 candidate

Version 1.0.0 candidate, updated 10 November 2026. **Not published.**
The MIT license remains a proposal. No license choice or public release has been
made on the author's behalf. The broader repository remains private.

The ZIP contains the original selected core and flight–hotel diagnostic, plus
the repaired service, selected tests and bounded trace checker with evidence.
There are 78 files, including the internal checksum manifest. The 32 added files
do not change the original proof modules or diagnostic; among prior members,
only the README and manifest changed. The source ZIP for either paper is separate.

The 9 November documentation update changes only `README.md` and its entry in
the internal checksum manifest. All proof sources, checkers, tests and reference
results are unchanged. The original candidate is preserved in the local review
backup. That candidate was checked from a separate extraction using a fresh
Python environment; full results are recorded in
`../../evidence/final_assurance_2026-11-09/`.

`zenodo-metadata.proposed.json` is prepared deposit text, not a submitted record.
Its open-access and MIT fields are proposed settings, not evidence of a license
grant or publication. Pending: author approval and release terms, Zenodo access,
public deposit, download/checksum verification, and the issued **version DOI**.
The DOI must then replace the pending-access wording in the author paper.

The final 10 November candidate was extracted and executed with existing tools.
The original core passed (14 exports, eight rejected mutations, nine tests,
2,048 matching records), as did 66 selected service tests and the six-history,
66-transition check. Five final states instantiate the existing closure theorem;
one remains undrained, and two inconsistent checker inputs are rejected. The
Python projection and provider contracts are not verified. See
[the evidence](../../research/service_refinement/README.md) and
[the packaging audit](../SERVICE_REPAIR_AUDIT_2026-11-10.json).
