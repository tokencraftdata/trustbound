import StripeGate

/- Irreversible observations accumulate by preservation of monotone predicates.
This corollary applies to the provider contract model, not an actual provider or API.
Observation witnesses below are semantic facts, not authenticated wire receipts.
-/
namespace TrustBoundStaggeredClosure
open TrustBoundAdmission TrustBoundStripeGate

theorem accumulate_stable_observations {S I : Type}
    (before : S → S → Prop) (fact : I → S → Prop)
    (preserves : ∀ i s t, before s t → fact i s → fact i t)
    (manifest : List I) (cut : S)
    (observed : ∀ i, i ∈ manifest → ∃ u, before u cut ∧ fact i u) :
    ∀ i, i ∈ manifest → fact i cut := by
  intro i member
  obtain ⟨u, earlier, truth⟩ := observed i member
  exact preserves i u cut earlier truth

theorem terminal_persists {s t : Provider}
    (run : ExternalRuns ApiStep s t) :
    ∀ i, i ∈ s.terminal → i ∈ t.terminal := by
  induction run with
  | refl => exact fun _ h => h
  | next step rest ih =>
    intro i member
    apply ih i
    cases step <;> simp_all

theorem staggered_terminal_closure {cut future : Provider}
    (past : ExternalRuns ApiStep start cut)
    (fenced : cut.core.closed = true)
    (observed : ∀ i, i ∈ cut.core.journal →
      ∃ u, ExternalRuns ApiStep u cut ∧ i ∈ u.terminal)
    (continuation : ExternalRuns ApiStep cut future) :
    future.core.rights = [] ∧ future.core.effects = cut.core.effects := by
  have resolved := accumulate_stable_observations
    (ExternalRuns ApiStep) (fun i s => i ∈ s.terminal)
    (fun i _ _ run truth => terminal_persists run i truth)
    cut.core.journal cut observed
  exact terminal_cut_stable past fenced resolved continuation

#print axioms accumulate_stable_observations
#print axioms terminal_persists
#print axioms staggered_terminal_closure
end TrustBoundStaggeredClosure
