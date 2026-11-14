# TrustBound paper

**TrustBound: Mechanized Completeness for Payment Epochs Initiated by AI Agents**
by Sandip Nandi, Aishwarya Bose, Apurba Bose and Soovadeep Bakshi
(Independent Researchers).

One paper serves both the arXiv posting and the NFM 2027 submission (regular
paper, Springer LNCS, 16 pages plus references).

| File | What it is |
|---|---|
| [lncs/](lncs/) | LaTeX source (LNCS format) |
| [TrustBound_Draft.pdf](TrustBound_Draft.pdf) | Compiled paper, 16 pages |
| [TrustBound_arXiv_Source.zip](TrustBound_arXiv_Source.zip) | arXiv upload: source, figures and `llncs.cls` |

## Build

From `lncs/`, run `pdflatex -interaction=nonstopmode -halt-on-error main.tex`
three times. The bibliography is embedded in `references.tex`. To rebuild the
arXiv ZIP, zip `main.tex`, `references.tex`, `figures/` and a copy of
`llncs.cls`, then check that the extracted ZIP compiles.

## Artifact

The artifact is this repository, which the paper links to directly. Before
posting, make the repository public. The [reviewer guide](../docs/REVIEWER_GUIDE.md) gives the
reproduction command; CI reruns it on Ubuntu and macOS for every push.

The code is MIT-licensed; the manuscript is distributed under arXiv's
non-exclusive license (see [LICENSE.md](LICENSE.md)).
