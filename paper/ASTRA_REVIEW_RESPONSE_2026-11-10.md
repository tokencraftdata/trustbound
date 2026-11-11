# Response to the seven manuscript notes

Reviewed against the latest service-repair draft and its recorded evidence on
10 November 2026. The notes are useful as a reader-accessibility check. They do
not identify a new counterexample or establish a novel result. The paper remains
a focused mechanization note.

| Point | Assessment and action |
|---|---|
| 1. Contribution and novelty | Already explicit in the abstract, introduction and related work: an explicit payment contract, checked models and reproducible examples of established principles. Kept that framing; added no novelty claim or extra disclaimer. |
| 2. Role of AI agents | Added an explicit introduction paragraph: agents are request-generating clients; planning and booking performance are not evaluated, and ordinary asynchronous applications face the same closure problem. |
| 3. Assumptions and implementation | Added concrete mechanisms and deployment obligations at the end of Section 4. A separate evidence matrix maps each premise to required evidence, existing mechanisms/tests and the unresolved obligation. This clarification does not prove those obligations. |
| 4. Implementation evidence | Expanded Section 5.3 with a six-scenario outcome table and the implementation-event projection. Explained the per-step correspondence checks, why an abandoned claim retains a right, why a lost reply retains the effect, and why merging commands depends on one effect per payment identity. Event capture and the Python projection remain trusted. |
| 5. Independent reproduction | The 78-file versioned candidate already contains source, checkers, selected tests, recorded traces, pinned Lean/pytest versions, commands and expected outputs. Prior extraction checks are recorded. Public or anonymous access remains a real blocker: no deposit, visibility change, DOI or publication was performed. The concise artifact appendix is retained. |
| 6. Accessibility | Defined epoch, effect, outstanding right and admission fence in the introduction using the hotel-payment example. The epoch's scope is fixed before admission; its admitted identities become fixed at the fence. Existing identity/amount/booking distinctions remain unchanged. |
| 7. Conclusions | Already bounded to conditional model results and selected implementation behaviors, with no production readiness or eventual-resolution claim. Kept the conclusion unchanged. |

The most substantive improvements are points 3 and 4. Points 2 and 6 are short
clarifications that prevent readers from inferring an AI capability evaluation.
Points 1 and 7 need no additional defensive wording. Point 5 needs a release
decision and accessible artifact, not more prose in the paper.

[Assumption-to-evidence matrix](../docs/ASSUMPTION_EVIDENCE.md) ·
[Executed service checks](../research/service_refinement/README.md) ·
[Release candidate](release/README.md)

This revision changes presentation only. The models, implementation, checkers,
test sources, recorded traces, result counts and versioned artifact are unchanged.
It checks the new table against saved traces and rebuilds both PDFs and source
archives. It does not rerun Lean, pytest, processor APIs or provider experiments.
An editorial audit records the build and integrity checks separately.
