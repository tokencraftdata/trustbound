# Anonymous workshop cut

Prepared from the author-reviewed arXiv note for a possible Agentic Software
Engineering workshop submission. This is a separate review version, not a
submission or a new scientific result.

The [workshop CFP](https://agenticse-aaai.github.io/), checked 6 November 2026,
lists a 20 November 2026 deadline at 23:59 Anywhere on Earth, a maximum of eight
pages excluding references for long papers, double-blind review, the AAAI-2027
Author Kit, non-archival publication, and in-person presentation by a registered
author. Non-archival status does not guarantee eligibility at a future venue;
that venue's policies remain controlling. The workshop's rule is distinct from
the main AAAI track's page limit.

Changes from the arXiv note:

- The author and affiliation are replaced by Anonymous Submission.
- Figure 1 and its callout are omitted; the completeness dependency figure is
  retained and renumbered automatically.
- Historical processor observations are condensed to three sentences.
- The membership-only refinement bridge is moved to content Appendix C.
- The bibliography uses the official author-year style. Content appendices stay
  before references and count toward the workshop's eight-page content limit.

`aaai2027.sty` and `aaai2027.bst` are unchanged files from the
[official author kit](https://aaai.org/authorkit27/), retrieved 6 November 2026.
Their original notices are preserved. No font sizes, margins or spacing in the
style file were modified to fit the page limit. The kit requires PDFLaTeX;
the Tectonic engine used for the arXiv note cannot compile this style.

Build in this directory with PDFLaTeX and BibTeX available:

```sh
pdflatex -halt-on-error main.tex
bibtex main
pdflatex -halt-on-error main.tex
pdflatex -halt-on-error main.tex
```

The compiled review PDF is `../TrustBound_Workshop_Anonymous.pdf` and the source
archive is `../TrustBound_Workshop_Source.zip`. Current preparation/build evidence
is recorded in `../DOI_RELEASE_PREP_AUDIT_2026-11-07.json`.
No author account, submission form, attendance commitment, public artifact
release or upload has been completed. The workshop's online form may impose
additional declarations or artifact/checklist requirements; those still need
to be checked before submission. The anonymous review PDF is not the copy to
post publicly on arXiv.

The 7 November revision adds the research objective and explains that running
the artifact yields a reproduction report, not a real merchant closure
certificate. It also states that public artifact access is pending. The review
PDF remains seven pages including references. No scientific claims were added.

The final reviewer edit condenses Section 7; this remains an anonymous review
copy. An identifying public-artifact DOI belongs in the author version; the
conference copy needs the venue-permitted anonymous artifact route.
