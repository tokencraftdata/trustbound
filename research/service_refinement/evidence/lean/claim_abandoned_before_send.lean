import StripeGate

open TrustBoundAdmission TrustBoundStripeGate

namespace claim_abandoned_before_send

def s0 : Provider := { objects := [], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s1 : Provider := { objects := [1], core := { journal := [], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s2 : Provider := { objects := [1], core := { journal := [1], issued := [], rights := [], effects := [], closed := false }, terminal := [] }

def s3 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := false }, terminal := [] }

def s4 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s5 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s6 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s7 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

def s8 : Provider := { objects := [1], core := { journal := [1], issued := [1], rights := [1], effects := [], closed := true }, terminal := [] }

theorem step0 : ApiStep s0 s1 := ApiStep.allocate s0 1 (by decide)

theorem step1 : ApiStep s1 s2 := ApiStep.register s1 1 (by decide) (by decide) (by decide)

theorem step2 : ApiStep s2 s3 := ApiStep.dispatch s2 1 (by decide) (by decide) (by decide) (by decide)

theorem step3 : ApiStep s3 s4 := ApiStep.fence s3

theorem step4 : ApiStep s4 s5 := ApiStep.waitOrReject s4

theorem step5 : ApiStep s5 s6 := ApiStep.waitOrReject s5

theorem step6 : ApiStep s6 s7 := ApiStep.waitOrReject s6

theorem step7 : ApiStep s7 s8 := ApiStep.waitOrReject s7

theorem recorded_run : ExternalRuns ApiStep start s8 := ExternalRuns.next step0 (ExternalRuns.next step1 (ExternalRuns.next step2 (ExternalRuns.next step3 (ExternalRuns.next step4 (ExternalRuns.next step5 (ExternalRuns.next step6 (ExternalRuns.next step7 (ExternalRuns.refl _))))))))

#print axioms recorded_run

theorem remains_undrained : s8.core.rights ≠ [] := by decide

#print axioms remains_undrained

end claim_abandoned_before_send

