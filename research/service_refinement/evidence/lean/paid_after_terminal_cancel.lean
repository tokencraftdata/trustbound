import StripeGate

open TrustBoundAdmission TrustBoundStripeGate

namespace paid_after_terminal_cancel

def s0 : Provider := { objects := [], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s1 : Provider := { objects := [1], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s2 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s3 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s4 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s5 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [], effects := [], closed := true }, terminal := [1] }

def s6 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [], effects := [1], closed := true }, terminal := [1, 1] }

theorem step0 : ApiStep s0 s1 := ApiStep.allocate s0 1 (by decide)

theorem step1 : ApiStep s1 s2 := ApiStep.register s1 1 (by decide) (by decide) (by decide)

theorem step2 : ApiStep s2 s3 := ApiStep.dispatch s2 1 (by decide) (by decide) (by decide) (by decide)

theorem step3 : ApiStep s3 s4 := ApiStep.fence s3

theorem step4 : ApiStep s4 s5 := ApiStep.canceled s4 1 (by decide)

theorem step5 : ApiStep s5 s6 := ApiStep.paid s5 1 (by decide)

theorem recorded_run : ExternalRuns ApiStep start s6 := ExternalRuns.next step0 (ExternalRuns.next step1 (ExternalRuns.next step2 (ExternalRuns.next step3 (ExternalRuns.next step4 (ExternalRuns.next step5 (ExternalRuns.refl _))))))

#print axioms recorded_run

def reported (id : Nat) : Prop := id ∈ [1]

theorem checked_exact {t : Provider} (future : ExternalRuns ApiStep s6 t) :

    (∀ id, id ∈ t.core.effects ↔ id ∈ s6.core.journal ∧ reported id) ∧ t.core.rights = [] := by

  apply reconciled_fence_complete (provider_runs_refine recorded_run) (by rfl) reported

    (by intro id _; simp [s6])

    (by intro id _; simp [reported, s6])

    (provider_runs_refine future)

#print axioms checked_exact

end paid_after_terminal_cancel

