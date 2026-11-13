# TrustBound manuscripts

The author draft was revised on **12 November 2026** with a concurrent-worker
evaluation in **Section 5.6 and Table 8**. Its 84 cases exercise 2/4/8 contending
clients, 2/4 payments, cancellation during dispatch, admission versus fencing,
and delayed provider observations. The experiment is recorded at `85f0846`.

The result includes a concrete limitation: **60 cases resolve, 18 remain pending,
and six are blocked by stale-read conflicts despite terminal source outcomes**.
An older truthful nonterminal response can arrive after terminal evidence and
persist a conflict that fresh reconciliation does not clear. The tests reproduce
this behavior; they do not fix it or establish conflict-free concurrency.

The earlier five-policy, 40-case serial comparison remains in Section 5.5.
The current suite passed **374 repository tests** and **157 selected package
tests**. The formal core, six Lean-projected histories and 864 serial schedules
are unchanged. Theorem 1, its proof, A1–A5, the Lean sources, and production
service code are unchanged. The shipped socket listener is still serial;
the new harness uses separate trusted workers and SQLite connections.
See the [concurrency revision audit](PAPER_CONCURRENCY_AUDIT_2026-11-12.json).
The [research-pass audit](PAPER_RESEARCH_PASS_AUDIT_2026-11-12.json) and
[earlier revision audit](PAPER_REVISION_AUDIT_2026-11-12.json) describe prior states.

The scenario table and mapping remain documented in the
[review response](ASTRA_REVIEW_RESPONSE_2026-11-10.md) and
[assumption evidence matrix](../docs/ASSUMPTION_EVIDENCE.md).

| Version | PDF | Source | Length |
|---|---|---|---|
| Author / arXiv, 12 November | [Author draft](TrustBound_Draft.pdf) | [LaTeX archive](TrustBound_arXiv_Source.zip) | 20 pages, 2 figures, 8 tables |
| Earlier anonymous review copy, 10 November | [Review copy](TrustBound_Workshop_Anonymous.pdf) | [LaTeX archive](TrustBound_Workshop_Source.zip) | 8 pages including references, 1 figure |

These are versions of the same note. **The anonymous copy has not yet been
synchronized with the 12 November revision.** The author version names
**Sandip Nandi — Independent Researcher**. The earlier conference version uses
the unchanged official AAAI 2027 template and omits identifying artifact links.
Both retain the AI-assistance disclosure.

## Artifact access and reproduction

Appendix A identifies the tested revision, versioned archive, checksum, content
ID, reproduction command, expected outputs, and successful cross-platform CI
run. It explicitly preserves the private-access and pending-release limitations;
no anonymous mirror or artifact DOI exists yet.

Runnable instructions are in [the reviewer guide](../docs/REVIEWER_GUIDE.md).
Historical run records, the test retry, field definitions and the flight–hotel
diagnostic are in [the supplementary record](SUPPLEMENTARY_RECORD.md).
The [current release candidate](release/README.md) retains the original formal
core and includes the repaired service, schedule checker, and scripted clients.
Its 158 selected tests are a subset of the 375 full-repository tests. The six
Lean-checked histories remain distinct from both the 864 Python schedules and
40 serial client cases and 84 concurrent-worker cases. The current version is
`1.1.0-review.5`; its ZIP and checksum
can be handed directly to a reviewer without granting repository access.
The SDK-dependent protocol and allocation repairs are outside this selected
package. A successful run checks conditional models and specified local
behaviors, not a merchant's real payments.

[CI run 43351357979](https://github.com/tokencraftdata/trustbound/actions/runs/43351357979)
passed for `85f0846` on Linux and macOS, reproducing all 84 concurrent-worker
outcomes, including the six stale-read conflicts. A separate Linux job passed
all 374 repository tests. Retained [Ubuntu](release/ci-run-43351357979/ubuntu-summary.json)
and [macOS](release/ci-run-43351357979/macos-summary.json) summaries match the
local package content ID; the [full-suite JUnit record](release/ci-run-43351357979/development-tests.xml)
is also retained because full CI attachments expire after 30 days. Separate CI
workers are not an independent research team's review. Earlier run directories
remain historical records.

## Build

From `arxiv/`, run:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Alternatively, the 12 November author revision was built with Tectonic 0.17.0:

```sh
tectonic --untrusted --keep-logs -r 2 main.tex
```

The author bibliography is embedded in `references.tex`. The conference copy
also requires BibTeX; see [its build instructions](workshop/README.md).
The current author source archive is extracted and rebuilt during document
verification; the revision audit records the comparison and visual checks.
This is document-build verification, not a fresh research run or a test of
arXiv's processing system. Earlier audits describe the anonymous build.

## Submission state

**Publication remains on hold at the author's request.** Work on the authorized
review branch does not submit the manuscript or publish a release. No public
release, DOI deposit, license grant, or submission is part of this revision.
The author reports an arXiv account and endorsement. Category eligibility,
license choices, artifact access and DOI, and the final processed-PDF check
remain to be resolved before submission.

See [submission status](SUBMISSION_STATUS.md),
[the submission guide](ARXIV_SUBMISSION_GUIDE.md),
[prepared metadata](arxiv-metadata.json), and
[the editorial audit](REVIEW_RESPONSE_AUDIT_2026-11-09.json).
Earlier dated audits describe earlier file states.

The earlier final-assurance run reproduced the selected research core with
fresh Python dependency installation and the existing Lean compiler. The bounded
result is historical; see
[the executed evidence](../evidence/final_assurance_2026-11-09/README.md) and
[the final audit](FINAL_ASSURANCE_AUDIT_2026-11-09.json). It does not establish
independent clean-machine reproduction, deployment correctness or novelty.

An earlier 10 November update cites primary Mastercard and Visa announcements in the
introduction. These sources motivate the setting; they do not validate the
model or establish novelty. That historical prose update did not change the research evidence.
See [the document audit](INDUSTRY_MOTIVATION_AUDIT_2026-11-10.json).
