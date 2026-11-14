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
disclosure. Runnable commands are in
[the core guide](../../docs/CORE_ARTIFACT.md). An anonymous reviewer link is
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
