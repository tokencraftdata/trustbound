# Anonymous conference review version

This is the review format of the TrustBound mechanization note, prepared with
the official AAAI 2027 template. It is **eight pages including references**;
the content ends on page 7. The PDF is `../TrustBound_Workshop_Anonymous.pdf`,
with a self-contained archive at `../TrustBound_Workshop_Source.zip`.

The [workshop CFP](https://agenticse-aaai.github.io/), checked 6 November 2026,
listed a 20 November deadline at 23:59 Anywhere on Earth, double-blind review,
eight pages excluding references for long papers, non-archival publication,
and in-person presentation by a registered author. Recheck the selected venue's
current rules and form before submission. No submission or attendance commitment
has been made.

Differences from the author version:

- The author line is anonymous and the identifying repository link is omitted.
- The architecture figure is omitted; the completeness figure remains.
- The unchanged membership-only transfer obligation is in Appendix B.
- References use the template's author–year bibliography style.

Appendix A contains only artifact availability and the retained AI-assistance
disclosure. Detailed commands, run history and the travel diagnostic are in
[the repository supplement](../SUPPLEMENTARY_RECORD.md), with runnable commands
in [the core guide](../../docs/CORE_ARTIFACT.md). An anonymous reviewer link is
pending. Do not insert the author's GitHub URL into this review copy.

`aaai2027.sty` and `aaai2027.bst` are unchanged files from the
[official author kit](https://aaai.org/authorkit27/), retrieved 6 November 2026.
Their notices are preserved. Build with PDFLaTeX and BibTeX:

```sh
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The 9 November review response clarifies the prose and diagnostic and adds nine
published foundations. The formal claim, scientific files and recorded results
are unchanged. See [the response](../REVIEW_RESPONSE_2026-11-09.md) and
[the build audit](../REVIEW_RESPONSE_AUDIT_2026-11-09.json).

Publication and submission remain on hold. No anonymous mirror, public artifact,
DOI, license grant or GitHub push was created in this revision.

Section 5 now records the final-assurance reproduction in a fresh Python virtual
environment on the same host, using the existing Lean compiler. The counts and
claim remain unchanged. [Execution record](../../evidence/final_assurance_2026-11-09/README.md).

The 10 November update adds the same short motivation paragraph and two
industry references as the author version. The unchanged cancellation paragraph
now precedes the theorem to avoid stretched column spacing. The review copy
was seven pages with the official template and anonymous metadata.
See [the document audit](../INDUSTRY_MOTIVATION_AUDIT_2026-11-10.json).

The subsequent 10 November service repair update adds Section 5.3: 66 selected
service tests and six histories checked against the existing model, with their
limits. That service-repair copy was seven pages, including references. The current
clarified copy is eight pages; Appendix B ends and references begin on page 7. The template, formal claim and assumptions are unchanged.
[Revision audit](../SERVICE_REPAIR_AUDIT_2026-11-10.json).

The latest editorial review defines the key terms, makes the AI-client role
explicit, and adds a scenario table and projection explanation. It changes no
formal claim, implementation or result. Reproduction commands remain in the
repository. [Response](../ASTRA_REVIEW_RESPONSE_2026-11-10.md) ·
[Audit](../ASTRA_REVIEW_AUDIT_2026-11-10.json).

The latest prose pass uses the purpose-led abstract opening and a clearer
introduction, trust-boundary explanation, evaluation and conclusion. The copy
remains eight pages. Assumptions, formal sections, result tables, citations,
source mapping and AI disclosure are unchanged. [Audit](../PURPOSE_PROSE_AUDIT_2026-11-10.json).

The subsequent readability pass simplifies the explanations of assumptions,
evidence and trace mapping, while retaining the approved opening and scientific
content. Local paragraph-break control avoids a single opening line at the end
of page 5; the template files are unchanged. The copy remains eight pages.
[Audit](../READER_PROSE_AUDIT_2026-11-10.json).
