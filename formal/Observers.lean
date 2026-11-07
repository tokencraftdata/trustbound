import Std

/-
Observer boundary, Lean 4.19.0; one fixed, authenticated epoch and cut.
`observes o p` means effective access to the full facts needed for path p's
closure assertion, NOT possession of a signing key or access to a copied log.
Corruption must include dependencies that can conceal those facts.
Reports are ideal authenticated positive attestations. Blind honest signers
may repeat incomplete source claims. This deliberately permissive report
model supplies the concealment condition for the necessity direction.
No concrete payment processor, cryptography, or route discovery is verified.
-/
namespace TrustBoundObservers

def Coverage {O P : Type} (required observes : O → P → Prop)
    (corrupt : O → Prop) : Prop :=
  ∀ p, ∃ o, required o p ∧ observes o p ∧ ¬ corrupt o

def Faithful {O P : Type} (observes : O → P → Prop) (corrupt : O → Prop)
    (good : P → Prop) (report : O → P → Prop) : Prop :=
  ∀ o p, ¬ corrupt o → observes o p → report o p → good p

def Accept {O P : Type} (required report : O → P → Prop) : Prop :=
  ∀ o p, required o p → report o p

def Robust {O P : Type} (required observes : O → P → Prop)
    (corrupt : O → Prop) : Prop :=
  ∀ good report, Faithful observes corrupt good report →
    Accept required report → ∀ p, good p

-- Exact for this report model and fixed required signer set. This is not
-- BFT consensus, availability, an optimal signer-selection algorithm, or
-- an unconditional necessity result for architectures with other evidence.
theorem robust_iff_coverage {O P : Type} (required observes : O → P → Prop)
    (corrupt : O → Prop) :
    Robust required observes corrupt ↔ Coverage required observes corrupt := by
  classical
  constructor
  · intro robust p
    apply Classical.byContradiction
    intro uncovered
    let good : P → Prop := fun q => q ≠ p
    let report : O → P → Prop := fun o q =>
      corrupt o ∨ ¬ observes o q ∨ q ≠ p
    have faithful : Faithful observes corrupt good report := by
      intro o q honest visible said
      rcases said with bad | blind | truth
      · exact False.elim (honest bad)
      · exact False.elim (blind visible)
      · exact truth
    have accepted : Accept required report := by
      intro o q needed
      by_cases same : q = p
      · subst q
        by_cases bad : corrupt o
        · exact Or.inl bad
        · have blind : ¬ observes o p := by
            intro visible
            exact uncovered ⟨o, needed, visible, bad⟩
          exact Or.inr (Or.inl blind)
      · exact Or.inr (Or.inr same)
    exact (robust good report faithful accepted p) rfl
  · intro covered good report faithful accepted p
    obtain ⟨o, needed, visible, honest⟩ := covered p
    exact faithful o p honest visible (accepted o p needed)

-- A policy must satisfy coverage for EVERY allowed coalition, not just
-- the coalition chosen after inspecting the accepted certificate.
theorem coalition_policy_iff {O P : Type} (required observes : O → P → Prop)
    (allowed : (O → Prop) → Prop) :
    (∀ corrupt, allowed corrupt → Robust required observes corrupt) ↔
    (∀ corrupt, allowed corrupt → Coverage required observes corrupt) := by
  constructor
  · intro robust corrupt admissible
    exact (robust_iff_coverage required observes corrupt).mp (robust corrupt admissible)
  · intro covered corrupt admissible
    exact (robust_iff_coverage required observes corrupt).mpr (covered corrupt admissible)

-- Witnesses derived only from an existing observation do not change its
-- equivalence classes, even if the original observation is retained too.
theorem derived_evidence_same {R V W : Type} (view : R → V) (witness : V → W)
    {a b : R} (same : view a = view b) :
    (view a, witness (view a)) = (view b, witness (view b)) := by
  rw [same]

-- `view r n` contains the ENTIRE available transcript through n, including
-- permitted queries. The hidden execution may depend on the stopping time.
-- No single permanently invisible payment or infinite message delay is needed.
theorem no_finite_closure_under_delayed_shadow {R V : Type}
    (view : R → Nat → V) (complete : R → Nat → Prop)
    (accept : Nat → V → Prop) (clean : R)
    (sound : ∀ r n, accept n (view r n) → complete r n)
    (shadow : ∀ n, ∃ hidden, view hidden n = view clean n ∧ ¬ complete hidden n) :
    ¬ ∃ n, accept n (view clean n) := by
  rintro ⟨n, accepted⟩
  obtain ⟨hidden, same, incomplete⟩ := shadow n
  apply incomplete
  apply sound hidden n
  rw [same]
  exact accepted

-- Nonvacuity: all reports can be present and faithful while one hidden path
-- is incomplete. The only effective observer is corrupt; the honest mirror
-- is not an independent effect observer. Unit denotes the single path.
example : Accept (fun (_ : Bool) (_ : Unit) => True) (fun _ _ => True) ∧
    Faithful (fun o (_ : Unit) => o = false) (fun o => o = false)
      (fun _ => False) (fun _ _ => True) ∧ ¬ (∀ _ : Unit, False) := by
  constructor
  · intro _ _ _; trivial
  constructor
  · intro o _ honest visible _; exact False.elim (honest visible)
  · intro all; exact all ()

-- Two truly observing required signers survive either single-signer fault.
example : ∀ bad : Bool, Coverage (fun (_ : Bool) (_ : Unit) => True)
    (fun _ _ => True) (fun o => o = bad) := by
  intro bad _
  cases bad with
  | false => exact ⟨true, True.intro, True.intro, by decide⟩
  | true => exact ⟨false, True.intro, True.intro, by decide⟩

-- An honest observer outside the REQUIRED set cannot secure acceptance.
example : ¬ Coverage (fun o (_ : Unit) => o = false)
    (fun _ _ => True) (fun o => o = false) := by
  intro covered
  obtain ⟨o, needed, _, honest⟩ := covered ()
  exact honest needed

-- Every delayed report arrives at a finite step, but there is no uniform
-- delay bound. Empty clean prefixes are indistinguishable from a report
-- scheduled one step later. The boolean denotes whether the report arrived;
-- its identical all-false prefix also means identical complete transcripts.
def arrivalView : Option Nat → Nat → Bool
  | none, _ => false
  | some arrival, n => decide (arrival ≤ n)

def arrivalComplete : Option Nat → Nat → Prop
  | none, _ => True
  | some arrival, n => arrival ≤ n

theorem delayed_arrival_instance :
    (∀ n, arrivalComplete none n) ∧
    (∀ arrival, ∃ n, arrivalComplete (some arrival) n) ∧
    (∀ n, ∃ hidden,
      (∀ k, k ≤ n → arrivalView hidden k = arrivalView none k) ∧
      ¬ arrivalComplete hidden n) := by
  refine ⟨fun _ => True.intro, ?_, ?_⟩
  · intro arrival; exact ⟨arrival, Nat.le_refl _⟩
  · intro n
    refine ⟨some (n + 1), ?_, ?_⟩
    · intro k hk
      simp only [arrivalView]
      have late : ¬ n + 1 ≤ k := by omega
      simp [late]
    · simp only [arrivalComplete]; omega

#print axioms robust_iff_coverage
#print axioms coalition_policy_iff
#print axioms derived_evidence_same
#print axioms no_finite_closure_under_delayed_shadow
#print axioms delayed_arrival_instance

end TrustBoundObservers
