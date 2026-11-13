import Admission
open TrustBoundAdmission

-- Canceling an unissued identity does not prevent a subsequent grant.
example : Runs initial ⟨[7], [7], [], [7], false⟩ := by
  let recorded : State := ⟨[7], [], [], [], false⟩
  let granted : State := ⟨[7], [7], [7], [], false⟩
  exact Runs.next (Step.record initial 7 rfl (by simp [initial]))
    (Runs.next (Step.cancel recorded 7)
      (Runs.next (Step.grant recorded 7 rfl (by simp [recorded]) (by simp [recorded]))
        (Runs.next (Step.deliver granted 7 (by simp [granted])) (Runs.refl _))))

-- The Lean Covered predicate does not require a fence.
example : Covered initial ∧ initial.closed = false := by
  simp [Covered, initial]
