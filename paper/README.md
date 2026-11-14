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
| [arxiv-metadata.json](arxiv-metadata.json) | Title, authors, abstract, categories and comments for the arXiv form |
| [ARXIV_SUBMISSION_GUIDE.md](ARXIV_SUBMISSION_GUIDE.md) | arXiv submission notes |
| [SUPPLEMENTARY_RECORD.md](SUPPLEMENTARY_RECORD.md) | Detailed run history and the flight–hotel diagnostic |
| [workshop/](workshop/) | Earlier anonymous AAAI-27 workshop version (8 pages, not synchronized) |

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
