import StripeGate

open TrustBoundAdmission TrustBoundStripeGate

namespace capture_across_fence

def s0 : Provider := { objects := [], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s1 : Provider := { objects := [1], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s2 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s3 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s4 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s5 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s6 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s7 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s8 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s9 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s10 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [], effects := [1], closed := true }, terminal := [1] }

def s11 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [], effects := [1], closed := true }, terminal := [1] }

def s12 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [], effects := [1], closed := true }, terminal := [1] }

theorem step0 : ApiStep s0 s1 := ApiStep.allocate s0 1 (by decide)

theorem step1 : ApiStep s1 s2 := ApiStep.register s1 1 (by decide) (by decide) (by decide)

theorem step2 : ApiStep s2 s3 := ApiStep.dispatch s2 1 (by decide) (by decide) (by decide) (by decide)

theorem step3 : ApiStep s3 s4 := ApiStep.waitOrReject s3

theorem step4 : ApiStep s4 s5 := ApiStep.waitOrReject s4

theorem step5 : ApiStep s5 s6 := ApiStep.waitOrReject s5

theorem step6 : ApiStep s6 s7 := ApiStep.waitOrReject s6

theorem step7 : ApiStep s7 s8 := ApiStep.waitOrReject s7

theorem step8 : ApiStep s8 s9 := ApiStep.fence s8

theorem step9 : ApiStep s9 s10 := ApiStep.paid s9 1 (by decide)

theorem step10 : ApiStep s10 s11 := ApiStep.waitOrReject s10

theorem step11 : ApiStep s11 s12 := ApiStep.waitOrReject s11

theorem recorded_run : ExternalRuns ApiStep start s12 := ExternalRuns.next step0 (ExternalRuns.next step1 (ExternalRuns.next step2 (ExternalRuns.next step3 (ExternalRuns.next step4 (ExternalRuns.next step5 (ExternalRuns.next step6 (ExternalRuns.next step7 (ExternalRuns.next step8 (ExternalRuns.next step9 (ExternalRuns.next step10 (ExternalRuns.next step11 (ExternalRuns.refl _))))))))))))

#print axioms recorded_run

def reported (id : Nat) : Prop := id ∈ [1]

theorem checked_exact {t : Provider} (future : ExternalRuns ApiStep s12 t) :

    (∀ id, id ∈ t.core.effects ↔ id ∈ s12.core.journal ∧ reported id) ∧ t.core.rights = [] := by

  apply reconciled_fence_complete (provider_runs_refine recorded_run) (by rfl) reported

    (by intro id _; simp [s12])

    (by intro id _; simp [reported, s12])

    (provider_runs_refine future)

#print axioms checked_exact

end capture_across_fence

