import Admission

/- Contract model of ONE constrained Stripe PaymentIntent path, not Stripe's
implementation. allocate means confirm=false, manual confirmation, no payment
method/customer/automation. All effect-capable calls require durable registration.
Provider-terminal means irreversibly no more effects, not a local status label.
No other credential, Dashboard, Billing, Checkout, Connect or mutation route is
allowed. These are explicit premises; documentation and probes do not prove them.
-/
namespace TrustBoundStripeGate
open TrustBoundAdmission

structure Provider where
  objects : List Nat
  core : State
  terminal : List Nat

def start : Provider := ⟨[], initial, []⟩

inductive ApiStep : Provider → Provider → Prop where
  | allocate (s : Provider) (id : Nat) (fresh : id ∉ s.objects) :
      ApiStep s { s with objects := id :: s.objects }
  | register (s : Provider) (id : Nat) (present : id ∈ s.objects)
      (isOpen : s.core.closed = false) (fresh : id ∉ s.core.journal) :
      ApiStep s { s with core := { s.core with journal := id :: s.core.journal } }
  | dispatch (s : Provider) (id : Nat) (isOpen : s.core.closed = false)
      (recorded : id ∈ s.core.journal) (unused : id ∉ s.core.issued)
      (notTerminal : id ∉ s.terminal) :
      ApiStep s { s with core := { s.core with
        issued := id :: s.core.issued, rights := id :: s.core.rights } }
  | paid (s : Provider) (id : Nat) (authorized : id ∈ s.core.rights) :
      ApiStep s { s with terminal := id :: s.terminal, core := { s.core with
        rights := s.core.rights.filter (· != id), effects := id :: s.core.effects } }
  | canceled (s : Provider) (id : Nat) (present : id ∈ s.objects) :
      ApiStep s { s with terminal := id :: s.terminal, core := { s.core with
        rights := s.core.rights.filter (· != id) } }
  | fence (s : Provider) : ApiStep s { s with core := { s.core with closed := true } }
  -- Lost replies, reads, intermediate processing and rejected late attempts
  -- can stutter. Remaining execution authority MUST stay in core.rights.
  | waitOrReject (s : Provider) : ApiStep s s

theorem provider_step_refines {s t : Provider} (h : ApiStep s t) :
    Runs s.core t.core := by
  cases h with
  | allocate => exact Runs.refl _
  | register id present op fresh =>
    exact Runs.next (Step.record s.core id op fresh) (Runs.refl _)
  | dispatch id op recorded unused nt =>
    exact Runs.next (Step.grant s.core id op recorded unused) (Runs.refl _)
  | paid id auth => exact Runs.next (Step.deliver s.core id auth) (Runs.refl _)
  | canceled id present => exact Runs.next (Step.cancel s.core id) (Runs.refl _)
  | fence => exact Runs.next (Step.fence s.core) (Runs.refl _)
  | waitOrReject => exact Runs.refl _

theorem provider_runs_refine {s t : Provider} (h : ExternalRuns ApiStep s t) :
    Runs s.core t.core :=
  simulate_runs Provider.core (fun _ _ step => provider_step_refines step) h

theorem unregistered_objects_inert {s : Provider} (h : ExternalRuns ApiStep start s)
    (id : Nat) (unregistered : id ∉ s.core.journal) :
    id ∉ s.core.rights ∧ id ∉ s.core.effects := by
  have covered := reachable_coverage (provider_runs_refine h)
  exact ⟨fun right => unregistered (covered id (Or.inl right)),
    fun effect => unregistered (covered id (Or.inr effect))⟩

theorem fenced_provider_coverage {s t : Provider}
    (past : ExternalRuns ApiStep start s) (closed : s.core.closed = true)
    (future : ExternalRuns ApiStep s t) :
    ∀ id, id ∈ t.core.rights ∨ id ∈ t.core.effects → id ∈ s.core.journal :=
  post_fence_coverage (provider_runs_refine past) closed (provider_runs_refine future)

def Discharged (s : Provider) : Prop :=
  ∀ id, id ∈ s.terminal → id ∉ s.core.rights

theorem step_discharged {s t : Provider} (h : ApiStep s t) (prior : Discharged s) :
    Discharged t := by
  cases h with
  | allocate => exact prior
  | register => exact prior
  | dispatch id op recorded unused nt =>
    intro x term right
    simp only [List.mem_cons] at right
    rcases right with rfl | old
    · exact nt term
    · exact prior x term old
  | paid id auth =>
    intro x term right
    have member := List.mem_filter.mp right
    simp only [List.mem_cons] at term
    rcases term with rfl | old
    · simp at member
    · exact prior x old member.1
  | canceled id present =>
    intro x term right
    have member := List.mem_filter.mp right
    simp only [List.mem_cons] at term
    rcases term with rfl | old
    · simp at member
    · exact prior x old member.1
  | fence => exact prior
  | waitOrReject => exact prior

theorem runs_discharged {s t : Provider} (h : ExternalRuns ApiStep s t)
    (prior : Discharged s) : Discharged t := by
  induction h with
  | refl => exact prior
  | next step rest ih => exact ih (step_discharged step prior)

theorem terminal_manifest_drains {s : Provider} (past : ExternalRuns ApiStep start s)
    (resolved : ∀ id, id ∈ s.core.journal → id ∈ s.terminal) : s.core.rights = [] := by
  have covered := reachable_coverage (provider_runs_refine past)
  have discharged := runs_discharged past (by simp [Discharged, start])
  cases h : s.core.rights with
  | nil => rfl
  | cons id rest =>
    have member : id ∈ s.core.rights := by simp [h]
    exact False.elim (discharged id (resolved id (covered id (Or.inl member))) member)

theorem terminal_cut_stable {s t : Provider} (past : ExternalRuns ApiStep start s)
    (closed : s.core.closed = true)
    (resolved : ∀ id, id ∈ s.core.journal → id ∈ s.terminal)
    (future : ExternalRuns ApiStep s t) :
    t.core.rights = [] ∧ t.core.effects = s.core.effects :=
  drained_fence_effects_stable (provider_runs_refine future) closed
    (terminal_manifest_drains past resolved)

#print axioms provider_step_refines
#print axioms provider_runs_refine
#print axioms unregistered_objects_inert
#print axioms fenced_provider_coverage
#print axioms terminal_manifest_drains
#print axioms terminal_cut_stable
end TrustBoundStripeGate
