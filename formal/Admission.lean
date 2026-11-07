import Std

/-
One path, one epoch, symbolic operation identities. `rights` is ALL effective
delivery authority (including queued/in-flight requests), not only a client queue.
`effects` is ghost history; `journal` is the durable authoritative source, not
an arbitrary API listing. A real deployment must refine EVERY action to Steps.
record/grant serialize with fence; journal never rolls back; cancel means
irrevocable disabling of ALL rights for that identity at the effect source.
These are explicit architecture premises, not inferred provider guarantees.
No signatures, persistence implementation, amount bounds or liveness are proved.
-/
namespace TrustBoundAdmission

structure State where
  journal : List Nat
  issued : List Nat
  rights : List Nat
  effects : List Nat
  closed : Bool
  deriving DecidableEq, Repr

def initial : State := ⟨[], [], [], [], false⟩

def Covered (s : State) : Prop :=
  ∀ id, id ∈ s.rights ∨ id ∈ s.effects → id ∈ s.journal

inductive Step : State → State → Prop where
  | record (s : State) (id : Nat) (isOpen : s.closed = false)
      (fresh : id ∉ s.journal) :
      Step s { s with journal := id :: s.journal }
  | grant (s : State) (id : Nat) (isOpen : s.closed = false)
      (recorded : id ∈ s.journal) (unused : id ∉ s.issued) :
      Step s { s with issued := id :: s.issued, rights := id :: s.rights }
  | deliver (s : State) (id : Nat) (authorized : id ∈ s.rights) :
      Step s { s with rights := s.rights.filter (· != id), effects := id :: s.effects }
  | cancel (s : State) (id : Nat) :
      Step s { s with rights := s.rights.filter (· != id) }
  | fence (s : State) : Step s { s with closed := true }

inductive Runs : State → State → Prop where
  | refl (s : State) : Runs s s
  | next {a b c : State} (step : Step a b) (rest : Runs b c) : Runs a c

theorem runs_trans {a b c : State} (ab : Runs a b) (bc : Runs b c) : Runs a c := by
  induction ab with
  | refl => exact bc
  | next step rest ih => exact Runs.next step (ih bc)

theorem step_preserves_coverage {s t : State} (h : Step s t) (covered : Covered s) :
    Covered t := by
  cases h with
  | record id op fresh =>
    intro x member
    exact List.mem_cons_of_mem id (covered x member)
  | grant id op recorded unused =>
    intro x member
    rcases member with right | effect
    · simp only [List.mem_cons] at right
      rcases right with rfl | prior
      · exact recorded
      · exact covered x (Or.inl prior)
    · exact covered x (Or.inr effect)
  | deliver id authorized =>
    intro x member
    rcases member with right | effect
    · exact covered x (Or.inl (List.mem_filter.mp right).1)
    · simp only [List.mem_cons] at effect
      rcases effect with rfl | prior
      · exact covered x (Or.inl authorized)
      · exact covered x (Or.inr prior)
  | cancel id =>
    intro x member
    rcases member with right | effect
    · exact covered x (Or.inl (List.mem_filter.mp right).1)
    · exact covered x (Or.inr effect)
  | fence => exact covered

theorem runs_preserve_coverage {s t : State} (h : Runs s t) (covered : Covered s) :
    Covered t := by
  induction h with
  | refl => exact covered
  | next step rest ih => exact ih (step_preserves_coverage step covered)

theorem reachable_coverage {s : State} (h : Runs initial s) : Covered s := by
  apply runs_preserve_coverage h
  simp [Covered, initial]

theorem closed_step {s t : State} (h : Step s t) (closed : s.closed = true) :
    t.closed = true ∧ t.journal = s.journal := by
  cases h with
  | record id op fresh => simp [closed] at op
  | grant id op recorded unused => simp [closed] at op
  | deliver id authorized => exact ⟨closed, rfl⟩
  | cancel id => exact ⟨closed, rfl⟩
  | fence => exact ⟨rfl, rfl⟩

theorem fenced_population_immutable {s t : State} (h : Runs s t)
    (closed : s.closed = true) : t.closed = true ∧ t.journal = s.journal := by
  induction h with
  | refl => exact ⟨closed, rfl⟩
  | next step rest ih =>
    have one := closed_step step closed
    have tail := ih one.1
    exact ⟨tail.1, tail.2.trans one.2⟩

-- Coverage of every future executed identity AND every remaining right at
-- the fence's immutable journal. This is derived, not a coverage premise.
theorem post_fence_coverage {s t : State} (reachable : Runs initial s)
    (closed : s.closed = true) (future : Runs s t) :
    ∀ id, id ∈ t.rights ∨ id ∈ t.effects → id ∈ s.journal := by
  have covered := reachable_coverage (runs_trans reachable future)
  have fixed := (fenced_population_immutable future closed).2
  intro id member
  rw [← fixed]
  exact covered id member

theorem drained_step {s t : State} (h : Step s t)
    (closed : s.closed = true) (drained : s.rights = []) :
    t.rights = [] ∧ t.effects = s.effects := by
  cases h with
  | record id op fresh => simp [closed] at op
  | grant id op recorded unused => simp [closed] at op
  | deliver id authorized => simp [drained] at authorized
  | cancel id => exact ⟨by simp [drained], rfl⟩
  | fence => exact ⟨drained, rfl⟩

-- No future debit event in the modeled epoch after the effect-source rights
-- are truly drained. Empty client work queues are not the `drained` premise.
theorem drained_fence_effects_stable {s t : State} (future : Runs s t)
    (closed : s.closed = true) (drained : s.rights = []) :
    t.rights = [] ∧ t.effects = s.effects := by
  induction future with
  | refl => exact ⟨drained, rfl⟩
  | next step rest ih =>
    have one := drained_step step closed drained
    have tail := ih (closed_step step closed).1 one.1
    exact ⟨tail.1, tail.2.trans one.2⟩

-- A complete journal plus truthful per-identity outcomes and irreversible
-- discharge covers all past effects and excludes future effects. `reported`
-- is an abstract observation: its truth and the journal export are external
-- obligations. This establishes identity coverage, not monetary accounting.
theorem reconciled_fence_complete {s t : State} (reachable : Runs initial s)
    (closed : s.closed = true) (reported : Nat → Prop)
    (settled : ∀ id, id ∈ s.journal → id ∉ s.rights)
    (truthful : ∀ id, id ∈ s.journal → (reported id ↔ id ∈ s.effects))
    (future : Runs s t) :
    (∀ id, id ∈ t.effects ↔ id ∈ s.journal ∧ reported id) ∧ t.rights = [] := by
  have covered := reachable_coverage reachable
  have drained : s.rights = [] := by
    cases h : s.rights with
    | nil => rfl
    | cons x xs =>
      have member : x ∈ s.rights := by simp [h]
      exact False.elim (settled x (covered x (Or.inl member)) member)
  have stable := drained_fence_effects_stable future closed drained
  refine ⟨?_, stable.1⟩
  intro id
  rw [stable.2]
  constructor
  · intro effect
    have recorded := covered id (Or.inr effect)
    exact ⟨recorded, (truthful id recorded).mpr effect⟩
  · intro evidence
    exact (truthful id evidence.1).mp evidence.2

-- Counterexecution is reachable through the guarded rules: the fence is
-- already closed, but an earlier delivery right can still produce an effect.
theorem fence_without_drain : ∃ s t,
    Runs initial s ∧ s.closed = true ∧ Step s t ∧ t.effects ≠ s.effects := by
  let recorded : State := ⟨[7], [], [], [], false⟩
  let armed : State := ⟨[7], [7], [7], [], false⟩
  let fenced : State := ⟨[7], [7], [7], [], true⟩
  let delivered : State := ⟨[7], [7], [], [7], true⟩
  refine ⟨fenced, delivered, ?_, rfl, ?_, by decide⟩
  · exact Runs.next (Step.record initial 7 rfl (by simp [initial]))
      (Runs.next (Step.grant recorded 7 rfl (by simp [recorded]) (by simp [recorded]))
        (Runs.next (Step.fence armed) (Runs.refl fenced)))
  · exact Step.deliver fenced 7 (by simp [fenced])

-- A bypass is NOT a valid Step. Allowing an extra external route destroys
-- the invariant while leaving journal evidence unchanged. This says nothing
-- about equality of a richer provider query transcript.
def bypass (s : State) (id : Nat) : State := { s with effects := id :: s.effects }

theorem bypass_breaks_coverage : ∃ s t,
    Runs initial s ∧ s.closed = true ∧ s.rights = [] ∧
    t = bypass s 9 ∧ t.journal = s.journal ∧ ¬ Covered t := by
  let s : State := { initial with closed := true }
  refine ⟨s, bypass s 9, Runs.next (Step.fence initial) (Runs.refl s),
    rfl, rfl, rfl, rfl, ?_⟩
  intro covered
  have impossible := covered 9 (Or.inr (by simp [bypass]))
  simp [s, initial, bypass] at impossible

-- Generic refinement bridge makes the remaining external premise explicit.
-- A real step may correspond to zero or several model steps. EVERY possible
-- action, including dashboards, other credentials and delayed dispatch, must
-- satisfy `simulate`. Neither our API probes nor this theorem supply it.
inductive ExternalRuns {R : Type} (step : R → R → Prop) : R → R → Prop where
  | refl (s : R) : ExternalRuns step s s
  | next {a b c : R} (one : step a b) (rest : ExternalRuns step b c) : ExternalRuns step a c

theorem simulate_runs {R : Type} {step : R → R → Prop} (abstract : R → State)
    (simulate : ∀ a b, step a b → Runs (abstract a) (abstract b))
    {a b : R} (h : ExternalRuns step a b) : Runs (abstract a) (abstract b) := by
  induction h with
  | refl => exact Runs.refl _
  | next one rest ih => exact runs_trans (simulate _ _ one) ih

theorem refinement_transfers_coverage {R : Type} {step : R → R → Prop}
    (abstract : R → State)
    (simulate : ∀ a b, step a b → Runs (abstract a) (abstract b))
    (realEffect realRight : R → Nat → Prop) (exportedJournal : R → List Nat)
    (preservesEffects : ∀ r id, realEffect r id → id ∈ (abstract r).effects)
    (preservesRights : ∀ r id, realRight r id → id ∈ (abstract r).rights)
    (faithfulJournal : ∀ r, exportedJournal r = (abstract r).journal)
    {start cut finish : R} (initial_state : abstract start = initial)
    (past : ExternalRuns step start cut) (future : ExternalRuns step cut finish)
    (closed : (abstract cut).closed = true) :
    ∀ id, realRight finish id ∨ realEffect finish id →
      id ∈ exportedJournal cut := by
  have reached := simulate_runs abstract simulate past
  rw [initial_state] at reached
  have coverage := post_fence_coverage reached closed (simulate_runs abstract simulate future)
  intro id liability
  rw [faithfulJournal cut]
  apply coverage id
  rcases liability with right | effect
  · exact Or.inl (preservesRights finish id right)
  · exact Or.inr (preservesEffects finish id effect)

#print axioms reachable_coverage
#print axioms fenced_population_immutable
#print axioms post_fence_coverage
#print axioms drained_fence_effects_stable
#print axioms reconciled_fence_complete
#print axioms fence_without_drain
#print axioms bypass_breaks_coverage
#print axioms refinement_transfers_coverage

end TrustBoundAdmission
