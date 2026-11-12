# TrustBound manuscripts

The author draft was revised on **12 November 2026** to state three concrete
contributions, explain Theorem 1 through successive hotel-payment states, and
separate enforced rules from deployment assumptions. Detailed checkout and
allowance repairs are now in Appendix B. The abstract describes the proof
content rather than counting exported declarations.

Section 5.5 reports a new comparison of **five scripted client policies across
40 cases**, using the actual restricted command service. These are request
behaviors, not LLM models. The experiment and reviewer artifact are recorded at
`aa82826`, with **355 full-repository tests**, **138 selected package tests**,
and the unchanged formal core, six projected histories, and 864 schedules.
Theorem 1, its proof, A1–A5, and the Lean sources remain unchanged.
See the [new research-pass audit](PAPER_RESEARCH_PASS_AUDIT_2026-11-12.json);
the [earlier revision audit](PAPER_REVISION_AUDIT_2026-11-12.json) describes the
preceding file state.

The scenario table and mapping remain documented in the
[review response](ASTRA_REVIEW_RESPONSE_2026-11-10.md) and
[assumption evidence matrix](../docs/ASSUMPTION_EVIDENCE.md).

| Version | PDF | Source | Length |
|---|---|---|---|
| Author / arXiv, 12 November | [Author draft](TrustBound_Draft.pdf) | [LaTeX archive](TrustBound_arXiv_Source.zip) | 19 pages, 2 figures, 7 tables |
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
Its 138 selected tests are a subset of the 355 full-repository tests. The six
Lean-checked histories remain distinct from both the 864 Python schedules and
40 client cases. The current version is `1.1.0-review.3`; its ZIP and checksum
can be handed directly to a reviewer without granting repository access.
The SDK-dependent protocol and allocation repairs are outside this selected
package. A successful run checks conditional models and specified local
behaviors, not a merchant's real payments.

[CI run 43293947080](https://github.com/tokencraftdata/trustbound/actions/runs/43293947080)
passed for `aa82826` on Linux and macOS, including all 40 client cases. The full
355-test suite also passed in a separate Linux job. Downloaded
[Ubuntu](release/ci-run-43293947080/ubuntu-summary.json) and
[macOS](release/ci-run-43293947080/macos-summary.json) summaries and the
[full-suite JUnit record](release/ci-run-43293947080/development-tests.xml) are
retained because complete CI attachments expire after 30 days. Both package
content IDs match version `1.1.0-review.3`. These are independent workers,
not an independent research team's reproduction. The earlier version's CI
summaries remain historical records in `release/ci-run-43196526546/`.

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
