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
