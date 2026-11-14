# arXiv submission guide

**Paper:** TrustBound: Mechanized Completeness for Payment Epochs Initiated by AI
Agents. **Authors:** Sandip Nandi, Aishwarya Bose, Apurba Bose and Soovadeep
Bakshi (Independent Researchers). **Target:** submit by 30 November 2026. The
same LNCS paper is the NFM 2027 submission (abstract 4 January, paper
11 January 2027); NFM allows prior arXiv posting.

## Before submitting

1. Make https://github.com/tokencraftdata/trustbound public. The paper links to
   it as the artifact.
2. Submit from one of the four authors' arXiv accounts, with an endorsement for
   cs.CR.

## Form choices

- **Primary category:** cs.CR (Cryptography and Security). **Cross-list:** cs.LO
  (Logic in Computer Science). The question concerns authorization, mediation
  and payment evidence; Lean and transition-system reasoning are the method.
  Moderators make the final placement.
- **License:** arXiv.org perpetual, non-exclusive license 1.0. It lets arXiv
  distribute the preprint without granting broader reuse rights, leaving them
  free for the later LNCS publication. A posted license cannot be revoked. [License guidance](https://info.arxiv.org/help/license/index.html).
- **Title, authors, abstract and comments:** copy them from
  [arxiv-metadata.json](arxiv-metadata.json). They use ASCII characters, as
  arXiv requires.

The code, Lean models and documentation are MIT-licensed separately (see
[LICENSE.md](LICENSE.md)).

## Upload

1. Upload [TrustBound_arXiv_Source.zip](TrustBound_arXiv_Source.zip). It contains
   `main.tex`, `references.tex`, `figures/` and `llncs.cls`, and it compiles with
   pdflatex to 16 pages.
2. Check arXiv's processed PDF, the metadata and the references before
   confirming.
3. Leave the journal reference and DOI empty until a version is published.

The paper discloses the use of OpenAI ChatGPT and Codex and Anthropic Claude,
following arXiv's
[generative-AI policy](https://info.arxiv.org/help/moderation/index.html).

To rebuild the ZIP after editing the paper, see [README.md](README.md#build).
