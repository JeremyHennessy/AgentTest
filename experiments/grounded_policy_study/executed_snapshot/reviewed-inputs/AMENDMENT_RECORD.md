# Prospective protocol amendment record

Adopted for implementation and final review on 2026-10-07 before any scientific stream, case or probe was generated. Scientific execution remains gated. This is an explicit change to computation and initial-worker order, not a reinterpretation of the original protocol.

The original v3 protocol remains unchanged. The published v2 API also remains unchanged at draft #223, commit cd74ab1db60bf650cc6730db95a4137d578e49df. No acceptance threshold, corpus, evidence intervention, endpoint, or simulator/CPU/memory/output/wall ceiling changed.

Changes:

- 64 deterministic producer constructions replace the original literal four-call construction budget. The four D-defined cohorts remain immutable, and every actual copy must match its layout reference before its own first selection.
- Both logical source sets and case slots are frozen first. Native identities bind exactly once after their ordinary creation. Serial combined create/read/reference/select/read workers replace separate creation and first-selection workers.
- Both complete first selections must still match before either owned action. Mismatches, including a later cohort mismatch, invalidate and stop the whole run.
- No retries, continuation or replacement cases. At most one globally terminal read-only reconciliation. Reports do not reopen the API. The old prospective reference to an audited continuation decision is superseded by this terminal-only contract.
- Existing no-copy/fork/reset safeguards and fixed v2 backend/uniform-prior/common-U requirements are retained explicitly. D-only cohort production is distinguished from current-context compilation of frozen rules.
- At most 384 normal capsule workers, 64 producer calls, 1,986 capsule validations and 4,486 independent D reconstructions, including the terminal reconciliation allowance. The complete resource composition and actual adapter still need separate review.

Review provenance:

- Original protocol SHA-256: 6f40f7bd8606a0e97f3f18eb4220347309e36892c0872bd4f5ff2721c6881241
- Preserved amendment review v1 SHA-256: 6594cea842a20396c3edf4d4ef911011986c986d9495b2df23ed3411151a6790
- Superseding amendment review v2 SHA-256: 7c0be59220df4b44d578c2a48c4859ba9db647712c768ff89e7701017d6e282f

The v1 separate-worker schedule is historical only. All active controller, choreography and resource contracts must use the v4 combined schedule. A new source freeze and independent pre-execution review are required before any scientific run.
