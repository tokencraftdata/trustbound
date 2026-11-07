# Manuscript under review

`TrustBound_Draft.pdf` is the 11-page **Option B mechanization note**, revised
6 November 2026: **TrustBound: A Mechanized Note on Payment-Epoch Completeness**.
The current contribution is the explicit A1–A5 contract and checked artifact,
with existing closure principles correctly attributed. Both diagrams remain.

This revision adds the six missing nearest-neighbor references: EffectBound,
Salas, AcquireBound, the formal agent-payment analysis, commit-time authorization,
and the individual IETF closure draft. Op is explicitly unversioned with an access
date. Table 2 is replaced by a short diagnostic account; suite retry details are
in the appendix; the Lean declaration list is a footnote.

A new finite flight–hotel diagnostic tested 18 trace records and 120 continuation
replays. It found no new exact-closure composition counterexample. The stale
capture maps to current-premise authorization; an unusable trip after cancellation
is a different business property. See [the executed comparison](../research/flight_hotel/README.md).
The existing Lean theorem and 70 previously tracked scientific source files are
unchanged. No provider calls or new machine-checked theorem were added.

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
[current revision audit](OPTION_B_AUDIT_2026-11-06.json). Sole authorship is confirmed; exact
publication name/affiliation, category, account eligibility and licenses remain
pending. No arXiv submission has occurred. The repository is private.

The [earlier candidate assessment](../docs/TRIP_CLOSURE_CANDIDATE.md) is retained
as history and points to the negative result. The previous diagram-revision audit
is historical; the current audit records this Option B revision.
