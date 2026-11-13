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
the original six-conflict run remains in the repository.
Retrieval holds the journal write lock, so slow reads block writers. Provider
freshness and terminality remain assumptions; genuine conflicts are retained.

The extracted package passed all 170 selected tests and the full reviewer
workflow in the existing pinned Python 3.12.14 environment with Lean 4.19.0.
The broader suite passed 403 tests. The formal 14/8/9/2,048 counts, six histories
with 64 transitions, 864 schedules, and 40 serial client cases are unchanged.
See the [local verification record](reviewer-verification-v1.1.0-review.6.json).
Reproduction reused the local environment; it is not independent scientific review.
The manifest binds the exact source inputs. The repository's CI workflow
rebuilds the package from each pushed revision and reproduces it on Ubuntu and
macOS workers; check the run for the revision you are using.

The existing MIT code license and separate manuscript terms are preserved.
Generating this candidate does not submit the paper, create a public mirror, or assign a DOI.

## Earlier candidates

Reviewer candidates `1.1.0-review.1` to `1.1.0-review.5`, the 1.0.0 core
candidate, and their verification and CI records have been removed from the
working tree to keep the repository focused. They remain available in the git
history (before the repository cleanup commit) if a historical record is needed.

## Zenodo deposit

`zenodo-metadata.proposed.json` is prepared deposit text, not a submitted record.
Its open-access and MIT fields are proposed settings, not evidence of a license
grant or publication. Pending: author approval and release terms, Zenodo access,
public deposit, download/checksum verification, and the issued **version DOI**.
The DOI must then replace the pending-access wording in the author paper.
