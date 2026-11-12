# TrustBound manuscripts

The author draft was revised on **12 November 2026** to explain a $200 hotel
payment from approval through a timeout, manual review, fencing, and
reconciliation. The opening explains why the agent is paused and why an
authorized payment may still complete as intended. Table 1 explains how its
permission is tracked. The draft documents the implementation repairs, adds
a claim-to-evidence table, and reports
the tested `fa218e4` implementation and `1.1.0-review.2` artifact. A1–A5, the
theorem and proof, the Lean sources, and the 23-reference bibliography are
unchanged. The abstract uses the research-paper wording approved on 12 November.
See the [revision audit](PAPER_REVISION_AUDIT_2026-11-12.json).

The scenario table and mapping remain documented in the
[review response](ASTRA_REVIEW_RESPONSE_2026-11-10.md) and
[assumption evidence matrix](../docs/ASSUMPTION_EVIDENCE.md).

| Version | PDF | Source | Length |
|---|---|---|---|
| Author / arXiv, 12 November | [Author draft](TrustBound_Draft.pdf) | [LaTeX archive](TrustBound_arXiv_Source.zip) | 17 pages, 2 figures, 4 tables |
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
core and includes the repaired service and bounded schedule checker. Its
123 selected tests are a subset of the 340 full-repository tests. The six
Lean-checked histories remain distinct from the 864 Python schedule cases.
The SDK-dependent protocol and allocation repairs are outside this selected
package. A successful run checks conditional models and specified local
behaviors, not a merchant's real payments.

[CI run 43196526546](https://github.com/tokencraftdata/trustbound/actions/runs/43196526546)
passed for `fa218e4` on Linux and macOS. The downloaded
[Ubuntu](release/ci-run-43196526546/ubuntu-summary.json) and
[macOS](release/ci-run-43196526546/macos-summary.json) summaries are retained here
because the complete CI attachments expire after 30 days. Their content IDs
match the selected release. These executions are separate from the earlier
same-host reproduction and are not independent scientific peer review.

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
model or establish novelty. The existing research evidence is unchanged.
See [the document audit](INDUSTRY_MOTIVATION_AUDIT_2026-11-10.json).
