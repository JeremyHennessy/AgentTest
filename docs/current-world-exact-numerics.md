# Bounded exact numeric resource repair

The frozen [`bb6d777b` preflight](https://github.com/JeremyHennessy/AgentTest/actions/runs/37646803715)
used three previously recorded zero-effect observations to construct new model
alternatives. North, east and west gained models, so all four actions had admitted
model sets within the existing grammar. Evaluation then stopped at the old
256-digit rational-component limit before preparing a case or selecting/executing
an action. That blocked result remains unchanged. This repair expands a numeric
resource envelope; it does not alter evidence, hypotheses, scores or preferences.

## Separate contract, same calculation

The new decision tag is `bounded-exact-fractions-8192-v1`. Only
`evaluate_bounded_exact` and `verify_bounded_exact_evaluation` opt into it. They
scope a larger component bound around the existing producer and independent proof
checker and restore the legacy bound on success or exception.

The ordinary `evaluate`, `verify_evaluation`, parsing and Brier paths keep their
256-digit default. Historical decisions without the new tag still use that
contract. Old fractions, cohort versions, case bodies and hashes are not rewritten.
Source-pinned research capsules keep their existing source-closure requirements.

Production still performs the same chronological `Fraction` likelihood updates,
normalizations and mixtures. It still computes entropy with the same 50-digit
Decimal context, half-even rounding, 18-place output, strict threshold, tie
comparison and movement order. There is no log-domain replacement, floating-point
approximation, evidence truncation or success-directed limit adjustment.

Exact decimal encoding/decoding uses small base-1,000,000,000 chunks when needed.
It preserves the canonical signed integer strings and reduced fraction pairs,
including values beyond Python's usual 4,300-digit conversion limit. It does not
change Python's process-global integer conversion settings.

## Fixed arithmetic and storage envelope

The named contract permits at most 8,192 evidence rows, 64 discovery rows, four
actions and eight models per action. Component magnitudes must be below
10^17,000. Input serialization is bounded at 8 MiB and a decision at 2 MiB. These
are explicit rejection boundaries, not promises that every row-bounded input will
fit. The existing 4 MiB checkpoint and every history/case/action/claim limit remain
in force. Oversized preparation fails before installing a case.

The numeric bound follows from the existing likelihoods, rather than a desired
result. In common denominator 120, a concrete model contributes 114 for a matching
outcome and 3 for another; the unresolved model contributes 40. With n matching
context/action observations and m <= 8 available models, unnormalized integer
masses are products of those factors, and their sum S_n <= 8 * 114^n. Posterior
denominators divide S_n. Likelihood products, partial sums and forecast mixtures
have denominators dividing 120 * S_n and remain between zero and one.

For n <= 8,192:

```
120 * 8 * 114^8192 < 10^17000
```

The proof quantity has 16,854 decimal digits and 55,985 bits. The full 17,000-digit
resource ceiling permits at most 56,473-bit components. `Fraction` addition uses
denominator GCD/LCM; multiplication/division cross-cancel before multiplying, so
this posterior/mixture path does not introduce an unaccounted squared denominator.
The argument does not cover arbitrary external rational arithmetic or Brier
squaring; those remain outside this new entrypoint contract.

Across all four actions a row is eligible for at most one exact-context/action
update. One producer plus one independent verification therefore performs at most
393,216 posterior rational arithmetic operations (8 multiplications, 8 divisions
and at most 8 additions per row per pass), plus small fixed mixture work. Bigint,
GCD and serialization cost grows with the bounded component size; this is not a
wall-clock runtime claim, nor a bound across repeated evaluations.

An authored consistent-outcome control crosses the legacy cap at update 125 and
needs 301 digits at update 146. The real frozen report contains 146 exact-context
east observations, explaining the newly exposed engineering boundary without
predicting any eventual action.

## Focused verification and next step

Authored checks cover exact equality with legacy decision bytes where the old
contract succeeds, unchanged ties, an independent integer-mass oracle at 146
updates, exact large-string round trips, fixed resource rejection and restoration
of the legacy scope after failure. Existing pure-policy controls retain the
threshold, rational and independent-verifier checks. No real full-history
reevaluation is performed locally.

The read-only preflight now identifies the candidate numeric contract and both
legacy/current component bounds. Release verification uses one updated read-only run against the full pinned
source and required CI, reporting selection, null or capacity deferral before any
possible live change. No action is guaranteed or
preferred by this repair.
