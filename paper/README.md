# Manuscript under review

`TrustBound_Draft.pdf` is the 11-page revision dated 6 November 2026 of
**TrustBound: A Mechanized Case Study of Payment-Epoch Completeness**.
It includes the trusted-service architecture and completeness-dependency diagrams
with explicit scope-limited captions. Two checked primary references on
root-scoped quiescence and budget conservation strengthen the contribution
boundary. The evaluation distinguishes the 6 November local export checks from
historical Stripe test-mode observations. No new theorem or provider result is
claimed. The abstract, conditional theorem and conclusion remain unchanged.

`arxiv/` contains three LaTeX files and two vector PDF figures.
`TrustBound_arXiv_Source.zip` contains those five files only, with relative paths.
It is a preparation package: exact author metadata is still pending.

The executed typesetting check uses Tectonic 0.17.0. From `arxiv/`:

```sh
tectonic --untrusted --keep-logs main.tex
```

The bibliography is embedded in `references.tex`; no BibTeX run is required.
Standard graphics packages and the included `figures/` directory are required.
The source archive was extracted and compiled separately with the existing
toolchain. arXiv's own processing remains to be checked during submission.

See [remaining submission work](SUBMISSION_STATUS.md) and the
[revision audit](REVISION_2026-11-06.json). Sole authorship is confirmed; exact
publication name/affiliation, category, account eligibility and licenses remain
pending. No arXiv submission has occurred. The repository is private.

The separate [trip-closure candidate](../docs/TRIP_CLOSURE_CANDIDATE.md) has no
new proved result or established priority claim in this draft.
