# Upload validation — 6 November 2026

Executed against the clean repository export, using the existing Python 3.12.14,
pytest 9.0.2 and Lean 4.19.0 installations on Apple Silicon macOS. The broader
tests reused installed pinned SDK dependencies. This was not a clean-machine
dependency installation or platform compatibility test. Each subprocess received
a minimal environment without provider credentials. No provider calls, bookings,
payments, Docker operations or account changes were performed.

| Executed check | Actual result |
|---|---|
| Selected core runner | Passed: 14 exported Lean results checked; eight premise-removal mutations rejected; nine baseline tests passed |
| Finite diagnostic | 2,048 records regenerated and matched the corrected historical result; strong comparator verdicts equal in all 512 groups |
| Full local test suite, initial restricted execution | 221 passed, one failed because the local service socket did not start |
| That one socket test, rerun with local socket permission | One passed; no source change between attempts |
| Paired local processor simulation | All 40 assertions passed; identical visible transcripts with 200 versus 300 synthetic units in the broader ledger |
| Diagram inspection | Both generated PNGs visually inspected; editable SVG and renderer included |
| Export check | All implementation, test and formal source copies matched the recorded source hashes; scan found no credential patterns, personal email addresses or local home paths |

All 222 test cases have therefore passed across the initial run and the focused
retry. This is not a claim that the initial full-suite invocation passed. The
socket test explicitly demonstrates that a separate process under the same user
does **not** establish credential isolation.

The core's nine tests are a subset of the 222, not additional independent tests.
The diagnostic reuses 64 distinct public inputs per arm. Strong labels share an
acceptance function; their tie is a consistency control. Mutation rejection
checks the selected proof scripts, not completeness of the threat model.

The 40-assertion simulation uses a local synthetic processor with an evaluation
ledger. It is neither a Stripe API run nor independent organizational witnessing.
Historical real Stripe test-mode results and the documentation-only Adyen review
are described separately in [provider evidence](PROVIDERS.md).

Sanitized execution summaries, test logs and JUnit results are retained in
[`evidence/upload_2026-11-06/`](../evidence/upload_2026-11-06/). Its provenance file
records original and exported hashes and the limited path/hostname substitutions.
Original logs remain outside the upload. No implementation was changed to obtain
these results. The manuscript PDF and LaTeX remain the existing author-review
draft; these upload checks do not change its claims or establish novelty.
