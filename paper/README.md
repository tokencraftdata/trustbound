# TrustBound manuscripts

The current versions retain the approved opening and use plainer explanations
of the model, trust assumptions, diagnostic and trace checks. The hotel-payment
example carries through the discussion. Formal definitions, A1–A5, theorem
statements and proofs, result counts, citations and AI disclosure are unchanged.
[Latest prose audit](READER_PROSE_AUDIT_2026-11-10.json).

The scenario table and mapping remain documented in the
[review response](ASTRA_REVIEW_RESPONSE_2026-11-10.md) and
[assumption evidence matrix](../docs/ASSUMPTION_EVIDENCE.md).

| Version | PDF | Source | Length |
|---|---|---|---|
| Author / arXiv | [Author draft](TrustBound_Draft.pdf) | [LaTeX archive](TrustBound_arXiv_Source.zip) | 14 pages, 2 figures |
| Anonymous conference review | [Review copy](TrustBound_Workshop_Anonymous.pdf) | [LaTeX archive](TrustBound_Workshop_Source.zip) | 8 pages including references, 1 figure |

These are two formats of the same note, not two separate papers. The author
version names **Sandip Nandi — Independent Researcher**. The conference version
uses the unchanged official AAAI 2027 template and omits identifying artifact
links. Both have 23 references and retain the AI-assistance disclosure.

## Artifact access and reproduction

Appendix A is now a short availability statement. The author draft links the
working repository and explicitly says it is private. Reviewer access is still
pending in the anonymous copy; no anonymous mirror or artifact DOI exists yet.

Runnable instructions are in [the core guide](../docs/CORE_ARTIFACT.md).
Historical run records, the test retry, field definitions and the flight–hotel
diagnostic are in [the supplementary record](SUPPLEMENTARY_RECORD.md).
The selected release candidate retains the original formal core and adds the
repaired service, selected tests and trace-check evidence. It was extracted and
rerun. A successful artifact run checks the conditional models and specified
local traces, not a merchant's real payments.

## Build

From `arxiv/`, run:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The author bibliography is embedded in `references.tex`. The conference copy
also requires BibTeX; see [its build instructions](workshop/README.md).
Both source archives were extracted and rebuilt. Their page text matches the
delivered PDFs. This is document-build verification, not a fresh research run
or a test of arXiv's processing system.

## Submission state

**Publication remains on hold at the author's request.** No upload, GitHub push,
public release, DOI deposit, license grant, or submission was performed.
The author reports an arXiv account and endorsement. Category eligibility,
license choices, artifact access and DOI, and the final processed-PDF check
remain to be resolved before submission.

See [submission status](SUBMISSION_STATUS.md),
[the submission guide](ARXIV_SUBMISSION_GUIDE.md),
[prepared metadata](arxiv-metadata.json), and
[the editorial audit](REVIEW_RESPONSE_AUDIT_2026-11-09.json).
Earlier dated audits describe earlier file states.

The subsequent final-assurance run reproduced the selected research core with
fresh Python dependency installation and the existing Lean compiler. The bounded
result is now stated in Section 5; see
[the executed evidence](../evidence/final_assurance_2026-11-09/README.md) and
[the final audit](FINAL_ASSURANCE_AUDIT_2026-11-09.json). It does not establish
independent clean-machine reproduction, deployment correctness or novelty.

An earlier 10 November update cites primary Mastercard and Visa announcements in the
introduction. These sources motivate the setting; they do not validate the
model or establish novelty. The existing research evidence is unchanged.
See [the document audit](INDUSTRY_MOTIVATION_AUDIT_2026-11-10.json).
