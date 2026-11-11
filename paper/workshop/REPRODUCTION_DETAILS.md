# Detailed reproduction record

These notes preserve the material removed from the conference paper's Appendix A
on 9 November 2026 to keep that appendix brief. The execution dates and counts
below remain historical; the editorial revision did not rerun research tests.
The selected release archive and its rights-pending status are unchanged.

A separate repository-export check on 6 November repeated the selected core
successfully and passed all 40 local simulator assertions, without provider
calls. The broader implementation suite initially passed 221 tests; one local
socket test passed on a focused retry with socket permission and unchanged
source. Thus all 222 cases passed across the two invocations, not in the initial
full-suite run. These implementation tests do not prove A1–A5 or executable
refinement; the nine diagnostic tests are included in the 222, not additional.


A selected-core archive is prepared; public release and reuse terms remain
pending. The private working repository is not public artifact access.

The accompanying minimal artifact contains the two Lean modules, their
checkers, the finite comparator and its nine tests, a reproduction runner,
reference output, and saved evidence. No payment credentials or provider SDK
are required. Use Lean 4.19.0 and Python with pytest 9.0.2; the executed Python
version was 3.12.14. From the artifact root, run:
```sh
python3 \
  scripts/reproduce_core_claim.py \
  --lean /path/to/lean \
  --output results/new-run
```
The output directory must not already exist. The runner copies the selected
inputs, supplies a small environment without payment credentials, disables
automatic pytest plugin loading, and writes command logs, source hashes, JUnit
output and a result summary. Expected totals are 14 exported results, eight
rejected mutations, nine passing tests, 2,048 records, and per-case strong-arm
agreement. No other historical module or full regression suite is silently
included in these counts.

In particular, `checks_passed: true` in `summary.json` reports
successful reproduction for the recorded inputs and tools. It does not report
that a merchant epoch is closed. The journal and source-terminal evidence of a
real deployment are not inputs to this runner.

Packaged logs replace local paths with declared tokens; the original
workspace evidence remains unchanged. A provenance file identifies original
and exported hashes. Hashes detect changes relative to the supplied manifest;
they are not independent witnesses of completeness or authorship. A clean
directory extraction check exercises the packaged files using the existing
toolchains, not an independent environment. Historical provider summaries are
clearly separated from the reproducible core.
Two additional reviewer examples in `review/AdmissionSemantics.lean`
check cancellation before a first grant and membership coverage without a
fence. They were separately compiled while reviewing the manuscript, are not
part of the 14-export count, and establish no new general security claim.

