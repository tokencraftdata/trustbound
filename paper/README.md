# Publication manuscripts

**TrustBound: A Mechanized Note on Payment-Epoch Completeness**

Author: **Sandip Nandi — Independent Researcher**. The 7 November 2026 revision
adds an explicit research objective and explains the outcome of running the
artifact. It preserves the conditional trusted-service claim, checked theorem,
nearest-work comparisons and negative flight–hotel finding.

- `TrustBound_Draft.pdf`: author version for arXiv, with two diagrams.
- `TrustBound_arXiv_Source.zip`: three LaTeX files and two PDF figures.
- `TrustBound_Workshop_Anonymous.pdf`: separate anonymous two-column conference
  review version in the official AAAI-2027 style, with one diagram.
- `TrustBound_Workshop_Source.zip`: conference sources, bibliography and template.
- `TrustBound_Core_Artifact.zip`: selected reproduction package, with release
  rights pending; this is not the entire research repository.

The goal is to make the premises for exact identity-level payment closure
inspectable. Running the core produces a checked reproduction report, not a
real merchant closure certificate. It does not establish deployment assumptions.

See [submission steps and recommendations](ARXIV_SUBMISSION_GUIDE.md),
[copyable metadata](arxiv-metadata.json), [submission status](SUBMISSION_STATUS.md),
[conference build instructions](workshop/README.md), and
[the current verification record](DOI_RELEASE_PREP_AUDIT_2026-11-07.json).
Earlier audits and execution records remain historical evidence.

To compile the author version, run from `arxiv/`:

```sh
tectonic --untrusted --keep-logs main.tex
```

The bibliography is embedded in `references.tex`; no BibTeX step is needed.
The source archive has relative figure paths. Local builds do not replace the
required arXiv processing check. The conference template instead requires
PDFLaTeX and BibTeX; its README gives the commands.

Neither version has been submitted. The repository remains private and no
public paper/code license has been granted. Author details and substantive
review are complete; account/endorsement, rights and artifact access remain.

Final reviewer update: Figure 1 shares page 3 with the body text; the author
PDF is 12 pages. The public DOI deposit remains blocked on Zenodo sign-in and
software-license selection. The [release candidate](release/README.md) is
prepared and checked, not published. Appendix A retains an honest pending-access
statement until an issued DOI and public files can be verified.
