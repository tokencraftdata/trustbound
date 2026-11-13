# Artifact release candidates

## Reviewer candidate 1.1.0-review.6

The [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.6.zip) and
[checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.6.zip.sha256) contain 45
entries. This version includes serialized retrieval/application, six new
reconciliation regression cases, an additional concurrency mutation, shared
experiment support, and reviewer timeout diagnostics. The ledger fix is tested
in the broader suite and remains outside this selected package.

The revised 84-case run resolves 66, leaves 18 genuinely pending, and has no
observation conflicts. No identity has more than one capture invocation or
payment effect. The six overlapping-read cases test the prevented ordering;
the original six-conflict run remains in the repository and the prior ZIP.
Retrieval holds the journal write lock, so slow reads block writers. Provider
freshness and terminality remain assumptions; genuine conflicts are retained.

The extracted package passed all 170 selected tests and the full reviewer
workflow in the existing pinned Python 3.12.14 environment with Lean 4.19.0.
The broader suite passed 403 tests. The formal 14/8/9/2,048 counts, six histories
with 64 transitions, 864 schedules, and 40 serial client cases are unchanged.
See the [local verification record](reviewer-verification-v1.1.0-review.6.json).
Reproduction reused the local environment; it is not independent scientific review.
The manifest binds the exact source inputs. Earlier CI records below concern
earlier revisions; they are not evidence for this repaired package.

The existing MIT code license and separate manuscript terms are preserved.
Generating this candidate does not submit the paper, create a public mirror, or assign a DOI.

## Historical reviewer candidate 1.1.0-review.5

The historical [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.5.zip) and
[checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.5.zip.sha256) contain 43
entries. This version adds the terminal-claim repair
([correctness fixes, section 6](../../docs/CORRECTNESS_FIXES.md)) and replaces
`RIGHTS_PENDING.txt` with the MIT `LICENSE`. The gate now refuses to claim a
command once its payment is observed terminal, so the late-capture history has
one rejected operation instead of a provider call: the six Lean-checked
histories now total 64 transitions (previously 66). All other formal,
diagnostic, schedule, client and concurrent-worker counts are unchanged, and
the stale-read limitation is still not fixed.

The extracted ZIP passed the full reviewer command on Linux (Python 3.13, Lean
4.19.0) in a fresh environment; all 158 selected tests passed and the full
repository suite passed 375 tests. The
[local verification record](reviewer-verification-v1.1.0-review.5.json) binds
the code revision, package content ID and recorded results. This is not an
independent review, and CI has not yet been re-run for this revision.

## Historical reviewer candidate 1.1.0-review.4

The historical [reviewer ZIP](TrustBound_Reviewer_Artifact_v1.1.0-review.4.zip) and
[checksum](TrustBound_Reviewer_Artifact_v1.1.0-review.4.zip.sha256) contain 43
entries. This version adds the [concurrent-worker evaluation](../../research/concurrent_clients/README.md),
19 regression tests, and full reference event transcripts. Its code revision is
`85f0846eeb06333b25e05bda537eda0c6d2ae976`.

The 84 cases include 60 resolved epochs, 18 genuinely pending epochs, and six
blocked by persistent stale-read conflicts despite terminal provider outcomes.
No identity has more than one observed capture invocation or payment effect.
**Successful reproduction includes this known limitation:** conflict-free
concurrent reconciliation is false. No production service code or Lean theorem
was changed, and the reconciliation limitation is not fixed.

The extracted ZIP passed the full reviewer command in the existing pinned
Python 3.12.14 environment with Lean 4.19.0. All 157 selected tests passed;
the broader repository suite separately passed 374 tests. The original formal,
diagnostic, trace, serial-schedule and serial-policy counts remain unchanged.
The [local verification record](reviewer-verification-v1.1.0-review.4.json)
binds the source hashes, package content ID and recorded results. This reused
local environment is not an independent review or a fresh setup.

[CI run 43351357979](https://github.com/tokencraftdata/trustbound/actions/runs/43351357979)
also passed all three jobs: extracted-package reproduction on Ubuntu 24.04 and
macOS 15 Intel, plus the full Linux regression suite. The
[retained records](ci-run-43351357979/run.json) bind the results to `85f0846`.
Both package content IDs and all reported counts match the local reproduction,
including the six stale-read conflicts. These workers are not an independent
scientific review.

The versioned ZIP can be supplied directly without granting repository access.
An anonymous/public mirror, DOI, and release terms remain pending. Earlier
archives remain immutable historical records.

## Earlier candidates

Reviewer candidates `1.1.0-review.1` to `1.1.0-review.3`, the 1.0.0 core
candidate, and their verification and CI records have been removed from the
working tree to keep the repository focused. They remain available in the git
history (before the repository cleanup commit) if a historical record is needed.

## Zenodo deposit

`zenodo-metadata.proposed.json` is prepared deposit text, not a submitted record.
Its open-access and MIT fields are proposed settings, not evidence of a license
grant or publication. Pending: author approval and release terms, Zenodo access,
public deposit, download/checksum verification, and the issued **version DOI**.
The DOI must then replace the pending-access wording in the author paper.
