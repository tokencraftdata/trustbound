import StripeGate

open TrustBoundAdmission TrustBoundStripeGate

namespace canceled_without_command

def s0 : Provider := { objects := [], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s1 : Provider := { objects := [1], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s2 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s3 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := true }, terminal := [] }

def s4 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := true }, terminal := [1] }

def s5 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := true }, terminal := [1] }

theorem step0 : ApiStep s0 s1 := ApiStep.allocate s0 1 (by decide)

theorem step1 : ApiStep s1 s2 := ApiStep.register s1 1 (by decide) (by decide) (by decide)

theorem step2 : ApiStep s2 s3 := ApiStep.fence s2

theorem step3 : ApiStep s3 s4 := ApiStep.canceled s3 1 (by decide)

theorem step4 : ApiStep s4 s5 := ApiStep.waitOrReject s4

theorem recorded_run : ExternalRuns ApiStep start s5 := ExternalRuns.next step0 (ExternalRuns.next step1 (ExternalRuns.next step2 (ExternalRuns.next step3 (ExternalRuns.next step4 (ExternalRuns.refl _)))))

#print axioms recorded_run

def reported (id : Nat) : Prop := id ∈ []

theorem checked_exact {t : Provider} (future : ExternalRuns ApiStep s5 t) :

    (∀ id, id ∈ t.core.effects ↔ id ∈ s5.core.journal ∧ reported id) ∧ t.core.rights = [] := by

  apply reconciled_fence_complete (provider_runs_refine recorded_run) (by rfl) reported

    (by intro id _; simp [s5])

    (by intro id _; simp [reported, s5])

    (provider_runs_refine future)

#print axioms checked_exact

end canceled_without_command

