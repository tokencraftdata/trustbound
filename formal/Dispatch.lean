import Std

/- One command identity per fixed payment action. Durable storage is atomic and
never rolls back committed state; crash clears only the volatile send ticket.
`sent` is ghost transport-invocation history, NOT provider debit history.
The trusted transport does not retry. Untrusted actors have no direct credential
or mutable access to this storage; a separate counterexample drops that premise.
No claim of exactly-once delivery, storage implementation verification or liveness.
-/
namespace TrustBoundDispatch

structure State where
  journal : List Nat
  grants : List Nat
  claimed : List Nat
  ticket : Option Nat
  sent : List Nat
  closed : Bool
  deriving DecidableEq, Repr

def initial : State := ⟨[], [], [], none, [], false⟩

inductive Step : State → State → Prop where
  | record (s : State) (id : Nat) (isOpen : s.closed = false) :
      Step s { s with journal := id :: s.journal }
  | grant (s : State) (id : Nat) (isOpen : s.closed = false)
      (recorded : id ∈ s.journal) : Step s { s with grants := id :: s.grants }
  | claim (s : State) (id : Nat) (granted : id ∈ s.grants)
      (recorded : id ∈ s.journal) (unused : id ∉ s.claimed) :
      Step s { s with claimed := id :: s.claimed, ticket := some id }
  | send (s : State) (id : Nat) (ticket : s.ticket = some id) :
      Step s { s with ticket := none, sent := id :: s.sent }
  | crash (s : State) : Step s { s with ticket := none }
  | fence (s : State) : Step s { s with closed := true }

inductive Runs : State → State → Prop where
  | refl (s : State) : Runs s s
  | next {s t u : State} (one : Step s t) (rest : Runs t u) : Runs s u

def Safe (s : State) : Prop :=
  s.sent.Nodup ∧
  (∀ id, id ∈ s.sent → id ∈ s.claimed ∧ id ∈ s.journal) ∧
  (∀ id, s.ticket = some id → id ∈ s.claimed ∧ id ∈ s.journal ∧ id ∉ s.sent)

theorem step_safe {s t : State} (step : Step s t) (safe : Safe s) : Safe t := by
  rcases safe with ⟨unique, covered, ticketSafe⟩
  cases step with
  | record id op =>
    refine ⟨unique, ?_, ?_⟩
    · intro x member
      exact ⟨(covered x member).1, List.mem_cons_of_mem id (covered x member).2⟩
    · intro x ticket
      have prior := ticketSafe x ticket
      exact ⟨prior.1, List.mem_cons_of_mem id prior.2.1, prior.2.2⟩
  | grant id op recorded => exact ⟨unique, covered, ticketSafe⟩
  | claim id granted recorded unused =>
    refine ⟨unique, ?_, ?_⟩
    · intro x member
      exact ⟨List.mem_cons_of_mem id (covered x member).1, (covered x member).2⟩
    · intro x same
      have eq : id = x := Option.some.inj same
      subst x
      exact ⟨by simp, recorded, fun member => unused (covered id member).1⟩
  | send id ticket =>
    have authority := ticketSafe id ticket
    refine ⟨List.nodup_cons.mpr ⟨authority.2.2, unique⟩, ?_, ?_⟩
    · intro x member
      simp only [List.mem_cons] at member
      rcases member with rfl | prior
      · exact ⟨authority.1, authority.2.1⟩
      · exact covered x prior
    · intro x impossible
      cases impossible
  | crash => exact ⟨unique, covered, by intro x impossible; cases impossible⟩
  | fence => exact ⟨unique, covered, ticketSafe⟩

theorem runs_safe {s t : State} (run : Runs s t) (safe : Safe s) : Safe t := by
  induction run with
  | refl => exact safe
  | next one rest ih => exact ih (step_safe one safe)

theorem reachable_safe {s : State} (run : Runs initial s) : Safe s := by
  apply runs_safe run
  simp [Safe, initial]

theorem dispatch_at_most_once {s : State} (run : Runs initial s) : s.sent.Nodup :=
  (reachable_safe run).1

theorem dispatch_has_durable_claim {s : State} (run : Runs initial s) :
    ∀ id, id ∈ s.sent → id ∈ s.claimed ∧ id ∈ s.journal :=
  (reachable_safe run).2.1

theorem closed_step {s t : State} (h : Step s t) (closed : s.closed = true) :
    t.closed = true ∧ t.journal = s.journal ∧ t.grants = s.grants := by
  cases h with
  | record id op => simp [closed] at op
  | grant id op recorded => simp [closed] at op
  | claim => exact ⟨closed, rfl, rfl⟩
  | send => exact ⟨closed, rfl, rfl⟩
  | crash => exact ⟨closed, rfl, rfl⟩
  | fence => exact ⟨rfl, rfl, rfl⟩

theorem fence_survives_crashes {s t : State} (future : Runs s t)
    (closed : s.closed = true) :
    t.closed = true ∧ t.journal = s.journal ∧ t.grants = s.grants := by
  induction future with
  | refl => exact ⟨closed, rfl, rfl⟩
  | next one rest ih =>
    have first := closed_step one closed
    have tail := ih first.1
    exact ⟨tail.1, tail.2.1.trans first.2.1, tail.2.2.trans first.2.2⟩

-- A committed claim can lose its volatile send opportunity without any send.
-- This explicitly refutes exactly-once/eventual-delivery claims for this design.
theorem crash_can_abandon_unsent_command : ∃ s t,
    Runs initial s ∧ s.claimed = [7] ∧ s.ticket = some 7 ∧ Step s t ∧
    t.sent = [] ∧ t.ticket = none ∧ 7 ∈ t.claimed := by
  let s : State := ⟨[7], [7], [7], some 7, [], false⟩
  let recorded : State := ⟨[7], [], [], none, [], false⟩
  let granted : State := ⟨[7], [7], [], none, [], false⟩
  refine ⟨s, {s with ticket := none}, ?_, rfl, rfl, Step.crash s, rfl, rfl, by simp [s]⟩
  exact Runs.next (Step.record initial 7 rfl)
    (Runs.next (Step.grant recorded 7 rfl (by simp [recorded]))
      (Runs.next (Step.claim granted 7 (by simp [granted]) (by simp [granted])
        (by simp [granted])) (Runs.refl s)))

def durableView (s : State) := (s.journal, s.grants, s.claimed, s.closed)

theorem identical_recovery_state_can_hide_send : ∃ s t,
    Runs initial s ∧ Runs initial t ∧ durableView s = durableView t ∧
    s.ticket = none ∧ t.ticket = none ∧ s.sent = [] ∧ t.sent = [7] := by
  let recorded : State := ⟨[7], [], [], none, [], false⟩
  let granted : State := ⟨[7], [7], [], none, [], false⟩
  let claimed : State := ⟨[7], [7], [7], some 7, [], false⟩
  let unsent : State := {claimed with ticket := none}
  let sent : State := {claimed with ticket := none, sent := [7]}
  have leadIn : ∀ u, Runs claimed u → Runs initial u := by
    intro u tail
    exact Runs.next (Step.record initial 7 rfl)
      (Runs.next (Step.grant recorded 7 rfl (by simp [recorded]))
        (Runs.next (Step.claim granted 7 (by simp [granted]) (by simp [granted])
          (by simp [granted])) tail))
  exact ⟨unsent, sent,
    leadIn unsent (Runs.next (Step.crash claimed) (Runs.refl unsent)),
    leadIn sent (Runs.next (Step.send claimed 7 rfl)
      (Runs.next (Step.crash sent) (Runs.refl sent))), rfl, rfl, rfl, rfl, rfl⟩

-- Add a credential-capable external sender: local gates cannot mediate it.
def RawSend (hasKey : Bool) (s t : State) : Prop :=
  hasKey = true ∧ t = {s with sent := 99 :: s.sent}

theorem credential_holder_bypasses_fence : ∃ s t,
    s.closed = true ∧ s.journal = [] ∧ RawSend true s t ∧
    99 ∈ t.sent ∧ 99 ∉ t.journal := by
  let s : State := {initial with closed := true}
  exact ⟨s, {s with sent := [99]}, rfl, rfl, ⟨rfl, rfl⟩,
    by simp, by simp [s, initial]⟩

#print axioms reachable_safe
#print axioms dispatch_at_most_once
#print axioms dispatch_has_durable_claim
#print axioms fence_survives_crashes
#print axioms crash_can_abandon_unsent_command
#print axioms identical_recovery_state_can_hide_send
#print axioms credential_holder_bypasses_fence
end TrustBoundDispatch
