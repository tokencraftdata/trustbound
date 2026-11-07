import Closure

/- Candidate audit: can the SAME independently capped payment model and
evidence justify a smaller retained budget? No. Its upper bound is attained by
an allowed continuation from every well-formed state. This is a model-relative
tightness proof, not a novel general least-reservation theorem or a provider
implementation proof. No probabilistic independence is assumed: the transition
system permits the pending cells to reach their caps in one combined run.
-/
namespace TrustBoundExposureOptimality
open TrustBound

inductive Advances : List Cell → List Cell → Prop where
  | refl (cs : List Cell) : Advances cs cs
  | next {a b c : List Cell} (step : LocalStep a b) (rest : Advances b c) :
      Advances a c

theorem prepend_advances (head : Cell) {a b : List Cell} (run : Advances a b) :
    Advances (head :: a) (head :: b) := by
  induction run with
  | refl => exact Advances.refl _
  | next step rest ih => exact Advances.next (LocalStep.tail head step) ih

theorem advances_run {a b : List Cell} (run : Advances a b) (closed : Bool) :
    Runs ⟨a, closed⟩ ⟨b, closed⟩ := by
  induction run with
  | refl => exact Runs.refl _
  | next step rest ih => exact Runs.next (Step.progress _ _ step) ih

theorem attain_cells (cs : List Cell) (wf : WellFormed cs) :
    ∃ ds, Advances cs ds ∧ totalActual ds = totalLiability cs := by
  induction cs with
  | nil => exact ⟨[], Advances.refl [], rfl⟩
  | cons c cs ih =>
    have wc : c.actual ≤ c.cap := wf c (by simp)
    obtain ⟨ds, run, amount⟩ := ih (fun x hx => wf x (by simp [hx]))
    cases terminal : c.terminal with
    | true =>
      refine ⟨c :: ds, prepend_advances c run, ?_⟩
      simp [totalActual, totalLiability, Cell.liability, terminal, amount]
    | false =>
      let paid : Cell := { c with actual := c.actual + (c.cap - c.actual) }
      have step : CellStep c paid :=
        CellStep.effect c (c.cap - c.actual) terminal (by omega)
      refine ⟨paid :: ds, Advances.next (LocalStep.head cs step)
        (prepend_advances paid run), ?_⟩
      simp only [totalActual, totalLiability, Cell.liability, terminal,
        Bool.false_eq_true, ↓reduceIte, paid, amount]
      omega

theorem future_exposure_attained (s : Epoch) (wf : WellFormed s.cells) :
    ∃ t, Runs s t ∧ totalActual t.cells = exposure (evidence s) := by
  obtain ⟨ds, run, amount⟩ := attain_cells s.cells wf
  refine ⟨⟨ds, s.closed⟩, ?_, ?_⟩
  · have h := advances_run run s.closed
    cases s
    exact h
  · simpa [evidence, exposure_eq] using amount

theorem future_bound_iff (s : Epoch) (bound : Nat)
    (closed : s.closed = true) (wf : WellFormed s.cells) :
    (∀ t, Runs s t → totalActual t.cells ≤ bound) ↔
      exposure (evidence s) ≤ bound := by
  constructor
  · intro safe
    obtain ⟨t, run, amount⟩ := future_exposure_attained s wf
    rw [← amount]
    exact safe t run
  · intro enough t run
    exact Nat.le_trans (closed_future_bound run closed wf) enough

-- Additional spend is a separate, disjoint expenditure against the SAME
-- cumulative budget. It is not a refund of already spent money, a new payment
-- API action, or capacity for an obligation excluded from the closed epoch.
theorem safe_extra_spend_iff (s : Epoch) (budget extra : Nat)
    (closed : s.closed = true) (wf : WellFormed s.cells) :
    (∀ t, Runs s t → totalActual t.cells + extra ≤ budget) ↔
      exposure (evidence s) + extra ≤ budget := by
  constructor
  · intro safe
    obtain ⟨t, run, amount⟩ := future_exposure_attained s wf
    rw [← amount]
    exact safe t run
  · intro enough t run
    have bound := closed_future_bound run closed wf
    omega

-- One paid item and two unresolved payments: L = 100 + 500 + 300 = 900.
-- With a 1000-unit cumulative budget, 100 more is safe; 101 is not.
def travel : Epoch := ⟨[⟨100, 100, true⟩, ⟨500, 0, false⟩,
  ⟨300, 0, false⟩], true⟩

theorem travel_wf : WellFormed travel.cells := by
  intro c member
  simp only [travel, List.mem_cons, List.not_mem_nil, or_false] at member
  rcases member with rfl | rfl | rfl <;> simp [Cell.WF]

example : ∀ t, Runs travel t → totalActual t.cells + 100 ≤ 1000 :=
  (safe_extra_spend_iff travel 1000 100 rfl travel_wf).mpr (by decide)

example : ¬ (∀ t, Runs travel t → totalActual t.cells + 101 ≤ 1000) := by
  rw [safe_extra_spend_iff travel 1000 101 rfl travel_wf]
  decide

#print axioms future_exposure_attained
#print axioms future_bound_iff
#print axioms safe_extra_spend_iff
end TrustBoundExposureOptimality
