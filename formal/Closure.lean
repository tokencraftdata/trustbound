import Std

/-
TrustBound closure kernel, Lean 4.19.0. No external libraries.
One epoch, one currency; a cell is an admitted operation with a hard effect cap.
`actual` is ghost rail state, NEVER an input to the executable auditor.
`finish` abstracts a truthful terminal rail response AND irrevocable disabling
of further effects for that operation. A timeout is NOT a finish event.
All effect paths must refine this transition system. That is an environmental
assumption, not something proved about Stripe, FedNow, or the Python prototype.
-/
namespace TrustBound

structure Cell where
  cap : Nat
  actual : Nat
  terminal : Bool
  deriving DecidableEq, Repr

def Cell.WF (c : Cell) : Prop := c.actual ≤ c.cap
def Cell.liability (c : Cell) : Nat := if c.terminal then c.actual else c.cap

inductive View where
  | pending (cap : Nat)
  | final (amount : Nat)
  deriving DecidableEq, Repr

def Cell.view (c : Cell) : View :=
  if c.terminal then .final c.actual else .pending c.cap

def View.exposure : View → Nat
  | .pending cap => cap
  | .final amount => amount

def View.done : View → Bool
  | .pending _ => false
  | .final _ => true

theorem view_exposure (c : Cell) : c.view.exposure = c.liability := by
  simp [Cell.view, Cell.liability]; split <;> rfl

theorem actual_le_liability {c : Cell} (h : c.WF) : c.actual ≤ c.liability := by
  simp only [Cell.liability]
  split
  · exact Nat.le_refl _
  · exact h

inductive CellStep : Cell → Cell → Prop where
  | effect (c : Cell) (d : Nat) (pending : c.terminal = false)
      (bounded : c.actual + d ≤ c.cap) :
      CellStep c { c with actual := c.actual + d }
  | finish (c : Cell) (pending : c.terminal = false) :
      CellStep c { c with terminal := true }

theorem cell_preserves {a b : Cell} (step : CellStep a b) (wf : a.WF) :
    b.WF ∧ b.liability ≤ a.liability ∧ a.actual ≤ b.actual := by
  cases step with
  | effect d pending bounded =>
    simp only [Cell.WF, Cell.liability, pending, Bool.false_eq_true, ↓reduceIte]
    exact ⟨bounded, Nat.le_refl _, Nat.le_add_right _ _⟩
  | finish pending =>
    simp only [Cell.WF, Cell.liability, pending, Bool.false_eq_true, ↓reduceIte]
    exact ⟨wf, wf, Nat.le_refl _⟩

def totalActual : List Cell → Nat
  | [] => 0
  | c :: cs => c.actual + totalActual cs

def totalLiability : List Cell → Nat
  | [] => 0
  | c :: cs => c.liability + totalLiability cs

def WellFormed (cs : List Cell) : Prop := ∀ c ∈ cs, c.WF

inductive LocalStep : List Cell → List Cell → Prop where
  | head {a b : Cell} (rest : List Cell) (h : CellStep a b) :
      LocalStep (a :: rest) (b :: rest)
  | tail (c : Cell) {a b : List Cell} (h : LocalStep a b) :
      LocalStep (c :: a) (c :: b)

theorem local_preserves {a b : List Cell} (h : LocalStep a b) (wf : WellFormed a) :
    WellFormed b ∧ totalLiability b ≤ totalLiability a ∧
      totalActual a ≤ totalActual b ∧ b.length = a.length := by
  induction h with
  | head rest h =>
    have w := cell_preserves h (wf _ (by simp))
    refine ⟨?_, ?_, ?_, rfl⟩
    · intro c hc
      simp only [List.mem_cons] at hc
      rcases hc with rfl | hc
      · exact w.1
      · exact wf c (by simp [hc])
    · simp only [totalLiability]; omega
    · simp only [totalActual]; omega
  | tail c h ih =>
    obtain ⟨wb, lb, ab, len⟩ := ih (fun x hx => wf x (List.mem_cons_of_mem c hx))
    refine ⟨?_, ?_, ?_, by simp [len]⟩
    · intro x hx
      simp only [List.mem_cons] at hx
      rcases hx with rfl | hx
      · exact wf _ (by simp)
      · exact wb x hx
    · simp only [totalLiability]; omega
    · simp only [totalActual]; omega

structure Epoch where
  cells : List Cell
  closed : Bool

inductive Step : Epoch → Epoch → Prop where
  | admit (s : Epoch) (cap : Nat) (isOpen : s.closed = false) :
      Step s { s with cells := ⟨cap, 0, false⟩ :: s.cells }
  | progress (s : Epoch) (cs : List Cell) (h : LocalStep s.cells cs) :
      Step s { s with cells := cs }
  | fence (s : Epoch) : Step s { s with closed := true }

inductive Runs : Epoch → Epoch → Prop where
  | refl (s : Epoch) : Runs s s
  | next {a b c : Epoch} (step : Step a b) (rest : Runs b c) : Runs a c

theorem step_wf {s t : Epoch} (h : Step s t) (wf : WellFormed s.cells) :
    WellFormed t.cells := by
  cases h with
  | admit cap op =>
    intro c hc
    simp only [List.mem_cons] at hc
    rcases hc with rfl | hc
    · exact Nat.zero_le _
    · exact wf c hc
  | progress cs h => exact (local_preserves h wf).1
  | fence => exact wf

theorem runs_wf {s t : Epoch} (h : Runs s t) (wf : WellFormed s.cells) :
    WellFormed t.cells := by
  induction h with
  | refl => exact wf
  | next step rest ih => exact ih (step_wf step wf)

theorem closed_step {s t : Epoch} (h : Step s t)
    (closed : s.closed = true) (wf : WellFormed s.cells) :
    t.closed = true ∧ totalLiability t.cells ≤ totalLiability s.cells ∧
      s.cells.length = t.cells.length := by
  cases h with
  | admit cap op => simp [closed] at op
  | progress cs h =>
    have p := local_preserves h wf
    exact ⟨closed, p.2.1, p.2.2.2.symm⟩
  | fence => exact ⟨rfl, Nat.le_refl _, rfl⟩

theorem closed_runs {s t : Epoch} (h : Runs s t)
    (closed : s.closed = true) (wf : WellFormed s.cells) :
    t.closed = true ∧ totalLiability t.cells ≤ totalLiability s.cells ∧
      s.cells.length = t.cells.length := by
  induction h with
  | refl => exact ⟨closed, Nat.le_refl _, rfl⟩
  | next step rest ih =>
    have p := closed_step step closed wf
    have q := ih p.1 (step_wf step wf)
    exact ⟨q.1, Nat.le_trans q.2.1 p.2.1, p.2.2.trans q.2.2⟩

theorem total_bound {cs : List Cell} (wf : WellFormed cs) :
    totalActual cs ≤ totalLiability cs := by
  induction cs with
  | nil => exact Nat.le_refl _
  | cons c cs ih =>
    have h := actual_le_liability (wf c (by simp))
    have ht := ih (fun x hx => wf x (by simp [hx]))
    simp only [totalActual, totalLiability]; omega

def evidence (s : Epoch) : List View := s.cells.map Cell.view
def exposure (vs : List View) : Nat := (vs.map View.exposure).sum

theorem exposure_eq (cs : List Cell) :
    exposure (cs.map Cell.view) = totalLiability cs := by
  induction cs with
  | nil => rfl
  | cons c cs ih =>
    simp only [exposure, List.map_cons, List.sum_cons] at *
    rw [view_exposure, ih]; rfl

-- Main safety theorem: certificate computed only from evidence bounds ALL
-- future cumulative debit effects of this closed epoch, under the step model.
theorem closed_future_bound {s t : Epoch} (h : Runs s t)
    (closed : s.closed = true) (wf : WellFormed s.cells) :
    totalActual t.cells ≤ exposure (evidence s) := by
  have p := closed_runs h closed wf
  have q := total_bound (runs_wf h wf)
  rw [evidence, exposure_eq]
  exact Nat.le_trans q p.2.1

theorem terminal_exact {cs : List Cell}
    (done : ∀ c ∈ cs, c.terminal = true) : totalActual cs = totalLiability cs := by
  induction cs with
  | nil => rfl
  | cons c cs ih =>
    have hc := done c (by simp)
    have ht := ih (fun x hx => done x (by simp [hx]))
    simp [totalActual, totalLiability, Cell.liability, hc, ht]

theorem local_requires_pending {a b : List Cell} (h : LocalStep a b) :
    ∃ c ∈ a, c.terminal = false := by
  induction h with
  | head rest h =>
    cases h with
    | effect d pending bounded => exact ⟨_, by simp, pending⟩
    | finish pending => exact ⟨_, by simp, pending⟩
  | tail c h ih =>
    obtain ⟨x, member, pending⟩ := ih
    exact ⟨x, List.mem_cons_of_mem c member, pending⟩

theorem closed_terminal_step {s t : Epoch} (h : Step s t)
    (closed : s.closed = true) (done : ∀ c ∈ s.cells, c.terminal = true) :
    t = s := by
  cases h with
  | admit cap op => simp [closed] at op
  | progress cs localStep =>
    obtain ⟨c, member, pending⟩ := local_requires_pending localStep
    have impossible := done c member
    simp [pending] at impossible
  | fence => cases s; simp_all

theorem closed_terminal_runs {s t : Epoch} (h : Runs s t)
    (closed : s.closed = true) (done : ∀ c ∈ s.cells, c.terminal = true) :
    t = s := by
  induction h with
  | refl => rfl
  | next step rest ih =>
    have eq := closed_terminal_step step closed done
    subst eq
    exact ih closed done

-- Exact closure is possible only after truthful, irrevocable terminalization
-- of EVERY admitted operation, including operations with zero final effects.
theorem closed_terminal_exact_future {s t : Epoch} (h : Runs s t)
    (closed : s.closed = true) (done : ∀ c ∈ s.cells, c.terminal = true) :
    totalActual t.cells = exposure (evidence s) := by
  rw [closed_terminal_runs h closed done, evidence, exposure_eq]
  exact terminal_exact done

-- Nonvacuity: an admitted payment may execute AFTER admission closes.
example : Runs ⟨[⟨100, 0, false⟩], true⟩ ⟨[⟨100, 75, true⟩], true⟩ := by
  apply Runs.next (Step.progress _ _ (LocalStep.head []
    (CellStep.effect ⟨100, 0, false⟩ 75 rfl (by decide))))
  apply Runs.next (Step.progress _ _ (LocalStep.head []
    (CellStep.finish ⟨100, 75, false⟩ rfl)))
  exact Runs.refl _

-- A conservative certificate is not an exact-effects certificate.
example : (Cell.mk 100 0 false).view = (Cell.mk 100 75 false).view := rfl
example : (Cell.mk 100 0 false).actual ≠ (Cell.mk 100 75 false).actual := by decide

-- General evidence boundary; no payment-specific axiom is hidden here.
def Sound {R V : Type} (view : R → V) (complete : R → Prop)
    (accept : V → Prop) : Prop := ∀ r, accept (view r) → complete r

-- Exact epistemic boundary over the chosen admissible-run universe R.
-- This characterizes possibility, NOT computability or finite-time liveness.
theorem certificate_possible_iff {R V : Type} (view : R → V)
    (complete : R → Prop) (r : R) :
    (∃ accept : V → Prop, Sound view complete accept ∧ accept (view r)) ↔
    (∀ other, view other = view r → complete other) := by
  constructor
  · rintro ⟨accept, sound, ok⟩ other same
    apply sound other
    rw [same]
    exact ok
  · intro known
    refine ⟨fun v => ∀ other, view other = v → complete other, ?_, known⟩
    intro other accepted
    exact accepted other rfl

theorem indistinguishable_no_sound_accept {R V : Type}
    (view : R → V) (complete : R → Prop) (accept : V → Prop)
    (clean hidden : R) (same : view clean = view hidden)
    (missing : ¬ complete hidden) (sound : Sound view complete accept) :
    ¬ accept (view clean) := by
  intro ok
  apply missing
  apply sound hidden
  rw [← same]
  exact ok

theorem witnesses_preserve_indistinguishability {R V W : Type}
    (view : R → V) (witness : V → W) {a b : R} (same : view a = view b) :
    witness (view a) = witness (view b) := congrArg witness same

-- Coalition-aware observer condition. A signature alone does not supply
-- `truthful`: an honest effect observer must check the path-local assertion.
theorem honest_observer_intersection {Observer Path : Type}
    (accepts : Observer → Path → Prop) (honest : Observer → Prop)
    (localAssertion : Path → Prop)
    (cover : ∀ p, ∃ o, accepts o p ∧ honest o)
    (truthful : ∀ o p, honest o → accepts o p → localAssertion p) :
    ∀ p, localAssertion p := by
  intro p
  obtain ⟨o, signed, good⟩ := cover p
  exact truthful o p good signed

-- Existence of an honest observer elsewhere is not acceptance coverage.
example : (∃ o : Bool, o = true) ∧ ¬ (∃ o : Bool, o = false ∧ o = true) := by
  decide

-- Composition needs no shared trip state; disjoint paths and a common unit
-- are a refinement obligation, not a consequence of arithmetic.
theorem path_sum_bound (actual caps : List Nat)
    (sameLength : actual.length = caps.length)
    (pointwise : ∀ i, i < actual.length → actual[i]! ≤ caps[i]!) :
    actual.sum ≤ caps.sum := by
  induction actual generalizing caps with
  | nil => simp
  | cons a rest ih =>
    cases caps with
    | nil => simp at sameLength
    | cons b tail =>
      have hab : a ≤ b := pointwise 0 (by simp)
      have ht := ih tail (by simpa using sameLength)
        (fun i hi => by simpa using pointwise (i + 1) (by simp; omega))
      simp only [List.sum_cons]; omega

#print axioms closed_future_bound
#print axioms terminal_exact
#print axioms closed_terminal_exact_future
#print axioms certificate_possible_iff
#print axioms indistinguishable_no_sound_accept
#print axioms witnesses_preserve_indistinguishability
#print axioms honest_observer_intersection
#print axioms path_sum_bound

end TrustBound
