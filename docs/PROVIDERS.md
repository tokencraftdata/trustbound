# Provider evidence

No provider calls are part of the repository upload or default reproduction.

| Provider | Executed work | Supported interpretation |
|---|---|---|
| Stripe | Saved 3 November test-mode path: 21 assertions, nine real HTTP requests, 200 test cents captured | Bounded behavior and reconciliation of known records. Complete admission coverage and credential isolation were not established. |
| Adyen | Official-documentation review of partial capture, cancellation and recovery; no API integration or payment test | An unresolved observation-to-terminality contract question, not a provider defect or new impossibility result. |
| Duffel / LiteAPI | Earlier test-environment booking probes; scripts retained | Supporting travel prototype history, not part of the paper's core proof or the upload's provider validation. |

Stripe cancellation is documented to prevent further charges through the named
PaymentIntent. This object-scoped contract does not inventory other objects or
activation routes. The model also restricts configuration and assumes exclusive
mediation. [Cancellation contract](https://docs.stripe.com/api/payment_intents/cancel).

Adyen documents that some technical capture failures can be repaired and
recaptured. Its initial successful CAPTURE event can precede a scheme rejection.
Our review did not establish whether cancelling an unused authorization also
disables recovery of an earlier capture modification. Nor did it establish that
such a guarantee is impossible or absent from all provider contracts.
[Capture](https://docs.adyen.com/online-payments/capture/),
[Failure handling](https://docs.adyen.com/online-payments/capture/failure-reasons).

The 60/30 EUR partial-capture example used in the research review was a proposed
scenario, not an executed trace. Keep remaining provider recovery represented
as outstanding authority until qualified evidence discharges it.

Saved non-sensitive Stripe and local-simulator summaries are in
`../evidence/historical/`. They are reported evidence, not independent replay of
raw private records. A processor view obtained with the same processor/key is
not an independently trusted issuer.

Provider scripts are research probes, not application onboarding or production
workflows. Do not interpret their presence as certification, UCP/AP2 interoperability,
or a proof that the provider meets every formal premise.
