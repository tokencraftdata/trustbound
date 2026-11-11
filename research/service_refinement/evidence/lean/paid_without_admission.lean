import StripeGate

open TrustBoundAdmission TrustBoundStripeGate

namespace paid_without_admission

def s0 : Provider := { objects := [], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s1 : Provider := { objects := [1], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s2 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s3 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := true }, terminal := [] }

def s4 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [1], closed := true }, terminal := [1] }

theorem step0 : ApiStep s0 s1 := ApiStep.allocate s0 1 (by decide)

theorem step1 : ApiStep s1 s2 := ApiStep.register s1 1 (by decide) (by decide) (by decide)

theorem step2 : ApiStep s2 s3 := ApiStep.fence s2

theorem step3 : ApiStep s3 s4 := ApiStep.paid s3 1 (by decide)

theorem recorded_run : ExternalRuns ApiStep start s4 := ExternalRuns.next step0 (ExternalRuns.next step1 (ExternalRuns.next step2 (ExternalRuns.next step3 (ExternalRuns.refl _))))

#print axioms recorded_run

def reported (id : Nat) : Prop := id ∈ [1]

theorem checked_exact {t : Provider} (future : ExternalRuns ApiStep s4 t) :

    (∀ id, id ∈ t.core.effects ↔ id ∈ s4.core.journal ∧ reported id) ∧ t.core.rights = [] := by

  apply reconciled_fence_complete (provider_runs_refine recorded_run) (by rfl) reported

    (by intro id _; simp [s4])

    (by intro id _; simp [reported, s4])

    (provider_runs_refine future)

#print axioms checked_exact

end paid_without_admission

