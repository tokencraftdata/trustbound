# Focused references

These sources explain the boundary; none establishes TrustBound's novelty or
supplies a complete real-deployment refinement. This is not an exhaustive review.

- **Chandy and Lamport, Distributed Snapshots (1985).** Global state and stable
  properties are established foundations, not new concepts introduced here.
  [Author-hosted paper](https://lamport.azurewebsites.net/pubs/chandy.pdf).
- **Dijkstra and Scholten, Termination Detection for Diffusing Computations.**
  Relevant background for detecting that outstanding work has finished.
  [Author manuscript, EWD687a](https://www.cs.utexas.edu/~EWD/transcriptions/EWD06xx/EWD687a.html).
- **Lee et al., RIFL: Implementing Linearizability at Large Scale and Low Latency
  (SOSP 2015).** Exactly-once RPC machinery is relevant to retries; our use of this
  reference distinguishes deduplication from a complete payment population.
  [Author-hosted paper](https://web.stanford.edu/~ouster/cgi-bin/papers/rifl.pdf).
- **AID-Guard v1.** Trusted effect boundaries and provider-qualified recovery.
  [Paper](https://arxiv.org/html/2608.21159v1).
- **Op: Compliance-Carrying Operations.** Remaining rights, truthful closure
  evidence and external completeness premises. Live author text, not a priority cutoff.
  [Paper](https://research.momentum.inc/papers/op.html).
- **HoldSpec v1.** Bounded authorization-hold lifecycle model with explicit
  scope limits. [Paper](https://arxiv.org/html/2610.14419v1).

Provider references and the distinction between actual test-mode work and
documentation review are in [provider evidence](PROVIDERS.md). The extra
foundational references and repository diagrams do not silently revise the
manuscript currently under author review.

## Missing nearest neighbors added in the Option B revision

The manuscript now also cites EffectBound (2609.02866v1), Salas (2609.31490v1),
AcquireBound (2609.14744v2), Jiang et al. (2609.00060v1), Santos-Grueiro's
commit-time authorization (2607.10487v2), and the individual closure Internet-Draft
`draft-watts-oauth-agent-revocation-closure-03`. Source definitions and their
relevance to the tested dependency are recorded in the
[flight–hotel comparison](../research/flight_hotel/README.md). The draft is a
work in progress, not an IETF standard. All were inspected on 6 November 2026.
