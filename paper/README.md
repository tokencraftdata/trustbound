# TrustBound manuscripts

The author draft was revised on **13 November 2026** to report the ledger-input
and reconciliation-ordering repairs. Section 5.6 and Table 8 now report **66
resolved cases, 18 genuinely pending cases, and no observation conflicts** in
84 bounded concurrent-worker cases. The six overlapping-read cases verify that
serialized retrieval/application prevents a newer read from overtaking a delayed
pending read. The earlier six-conflict result remains historical evidence.

The write transaction spans each external read, blocking journal writers.
Adapters must bound transport timeouts and avoid journal re-entry. Provider-side
stale responses and existing conflicts are not repaired. Appendix B describes
direct-ledger validation; historical invalid balances are not migrated.

The maintenance pass extracts shared experiment plumbing and separates reviewer
runner stages, preserving partial diagnostics on timeout. Its scenario oracles
remain independent. **403 repository tests** and **170 selected package tests**
passed. The Lean sources, Theorem 1, proof, and A1–A5 are unchanged. Six projected
histories now contain 64 transitions after the remote terminal-claim repair;
The 864 serial schedules and the 40-case client comparison are reproduced.
See the [repair and maintenance audit](PAPER_MAINTENANCE_AUDIT_2026-11-13.json).

| Version | PDF | Source | Length |
|---|---|---|---|
| Author / arXiv, 13 November | [Author draft](TrustBound_Draft.pdf) | [LaTeX archive](TrustBound_arXiv_Source.zip) | 20 pages, 2 figures, 8 tables |
| Earlier anonymous review copy, 10 November | [Review copy](TrustBound_Workshop_Anonymous.pdf) | [LaTeX archive](TrustBound_Workshop_Source.zip) | 8 pages including references, 1 figure |

The author version names **Sandip Nandi — Independent Researcher**. The anonymous
copy uses the official AAAI 2027 format and has not been synchronized with this
revision. Both retain the AI-assistance disclosure. Historical audits describe
[the original concurrency finding](PAPER_CONCURRENCY_AUDIT_2026-11-12.json),
[the research pass](PAPER_RESEARCH_PASS_AUDIT_2026-11-12.json), and
[the earlier revision](PAPER_REVISION_AUDIT_2026-11-12.json).

## Artifact access and reproduction

Use [the reviewer guide](../docs/REVIEWER_GUIDE.md) and
[reviewer candidate 1.1.0-review.6](release/README.md). Its 45-entry ZIP includes
pinned dependencies, a per-file manifest, and a reproduction command. The
[local verification record](release/reviewer-verification-v1.1.0-review.6.json)
binds its hashes to the results. Local reproduction used the existing pinned
Python environment and Lean installation, from a fresh extraction outside the
checkout. The selected 170 tests are a subset of the full 403 tests.

The archive can be supplied without repository access after setup. The repository remains private; an anonymous/public mirror and DOI are pending.
The existing MIT code license and separate manuscript terms are retained.
The SDK-dependent protocol/allocation/ledger modules remain outside the selected
archive. No real-provider request was made by the new checks.

[CI run 43351357979](https://github.com/tokencraftdata/trustbound/actions/runs/43351357979)
is historical: it verified the earlier 85f0846 revision on Linux and macOS with
six expected stale-read conflicts. Its [retained summaries](release/ci-run-43351357979/run.json)
do not certify the repaired revision. The workflow runs on each new push;
observed results must be identified by the tested revision and content ID.

## Build

From `arxiv/`, use three passes of `pdflatex -interaction=nonstopmode -halt-on-error main.tex`,
or `tectonic --untrusted --keep-logs -r 2 main.tex` (Tectonic 0.17.0).
The bibliography is embedded in `references.tex`. The source ZIP is separately
extracted and rebuilt; all page text is compared and rendered pages inspected.
The [anonymous build instructions](workshop/README.md) also require BibTeX.

## Submission state

**Publication remains on hold at the author's request.** This work does not
submit the paper, publish a public release, assign a DOI, or change the existing license terms.
The author reports an arXiv account and endorsement. See
[submission status](SUBMISSION_STATUS.md), [submission guide](ARXIV_SUBMISSION_GUIDE.md),
and [prepared metadata](arxiv-metadata.json). Reviewer access, final venue format,
venue requirements and the final processed-PDF check remain outstanding.
