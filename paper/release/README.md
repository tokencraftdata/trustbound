# Public artifact release candidate

Version 1.0.0 candidate, updated 10 November 2026. **Not published.**
The MIT license remains a proposal. No license choice or public release has been
made on the author's behalf. The broader repository remains private.

The ZIP contains the original selected core and flight–hotel diagnostic, plus
the repaired service, selected tests and bounded trace checker with evidence.
There are 78 files, including the internal checksum manifest. The 32 added files
do not change the original proof modules or diagnostic; among prior members,
only the README and manifest changed. The source ZIP for either paper is separate.

The 9 November documentation update changes only `README.md` and its entry in
the internal checksum manifest. All proof sources, checkers, tests and reference
results are unchanged. The original candidate is preserved in the local review
backup. That candidate was checked from a separate extraction using a fresh
Python environment; full results are recorded in
`../../evidence/final_assurance_2026-11-09/`.

`zenodo-metadata.proposed.json` is prepared deposit text, not a submitted record.
Its open-access and MIT fields are proposed settings, not evidence of a license
grant or publication. Pending: author approval and release terms, Zenodo access,
public deposit, download/checksum verification, and the issued **version DOI**.
The DOI must then replace the pending-access wording in the author paper.

The final 10 November candidate was extracted and executed with existing tools.
The original core passed (14 exports, eight rejected mutations, nine tests,
2,048 matching records), as did 66 selected service tests and the six-history,
66-transition check. Five final states instantiate the existing closure theorem;
one remains undrained, and two inconsistent checker inputs are rejected. The
Python projection and provider contracts are not verified. See
[the evidence](../../research/service_refinement/README.md) and
[the packaging audit](../SERVICE_REPAIR_AUDIT_2026-11-10.json).
