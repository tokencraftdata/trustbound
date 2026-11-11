# Final artifact assurance — 9 November 2026

Both the original frozen candidate and the documentation-updated candidate
passed the selected-core runner. Each checked **14 exported Lean results**, rejected
**eight altered proofs**, passed **nine tests** without failures/errors/skips, and
reproduced **2,048 records** byte-for-byte against the saved reference.

pytest 9.0.2 and its dependencies were installed from PyPI into a new virtual
environment. The base Python 3.12.14 runtime, Lean 4.19.0 compiler and macOS host
were reused. This is fresh Python dependency setup, **not independent clean-machine
reproduction**. The first dependency-download attempt was blocked by sandbox DNS;
the network-enabled install succeeded. Both core executions passed without retry.

The candidate's only changed ZIP members are `README.md` and `SHA256SUMS.json`.
The first run precedes that documentation update; `execution-final/` checks the
exact final candidate. All 114 existing scientific files in the prior manifest
remain unchanged. No provider requests, new theorem, or full implementation-suite
run occurred. Existing proof mutations are dependency checks, not minimality results.

`REPORT.json` binds the archive hashes, environment, sources and outcomes.
`PROVENANCE.json` maps original to path-redacted logs. `installed-requirements.txt`
and `downloaded-dependencies.json` record the actual package versions and download
hashes. The unchanged runner's `new_dependencies_installed: false` describes its
own stage; the outer preparation installed dependencies as recorded here.

The raw executions are retained in the local research workspace. This export
omits duplicate source snapshots and diagnostic data already present in the
repository; their hashes are in the reports. The artifact remains unpublished,
the repository private, and release terms/DOI pending author approval.
