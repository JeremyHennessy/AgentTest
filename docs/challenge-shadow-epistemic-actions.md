# Challenge shadow evidence-driven action selection

Status: isolated research only. No live challenge-world action authority.

Production base: `73d4765322efd8c7b87ed8c94bdca8bb81098d7a`.

This experiment follows completed shadow-native loop PR #191.

## Question

Can a shadow policy choose the **next challenge action** from:

- the current public challenge observation;
- the current native temporal inquiry;
- persisted aggregate public action/change associations;

without raw trace history, hidden world state, reward, goal, solution guidance, or live Ora action authority?

The chosen action must be exactly reproducible after recorder reload and must support the same native outcome-resolution path already verified in #191.

## Policy

The adapter preserves the frozen `public-falsification-oriented-v1` rule:

1. Enumerate only commands available from the current public observation.
2. For each command, look up persisted action exposure for the selected temporal feature.
3. If any command has fewer than two evaluable action-present samples, choose the least-sampled command using the frozen generic action-order/tie-break rule.
4. Otherwise estimate public change probability with the same Beta(1,1) smoothing and score:
   `falsification_probability * (0.25 + 0.75 * evidence_weight)`.
5. Choose the highest score using the frozen action/tie-break ordering.

For a `same_next_observation` inquiry, observed change is falsifying. For `changes_next_observation`, observed sameness is falsifying.

The adapter receives already persisted association summaries from the challenge recorder. It does not receive a raw observation/receipt prefix.

## Evidence-sensitivity control

Each layout also computes the choice with an empty association set.

At least one of four layouts must choose a different command when persisted evidence is removed. This is a bounded counterfactual proving the evidence changes the selector's behavior rather than merely being attached to an unchanged command.

The ordinary unguided least-tried command is also recorded for comparison, but differing from it is measured rather than required.

## Four-layout protocol

Each layout uses a separate copy of the same pinned Ora state used in #191:

`autonomous/growth@825d2c86759f5b7aacbf4e5dd98b5`

Correction: the actual immutable state SHA used by the workflow is
`825d2c86759f5f4065807508ab7fbfe3462feb8a`.

For each layout:

1. stream 600 challenge transitions with the reviewed external explorer;
2. publish the same frozen information-gain temporal inquiry;
3. stage it into copied Ora through the verified integration;
4. run one ordinary copied Core cycle and preserve native `awaiting_native_evidence`;
5. obtain persisted public action associations from the recorder;
6. select the next command;
7. reload the recorder and require byte-equivalent associations plus exact selection output;
8. compute an empty-association counterfactual and unguided command;
9. execute exactly one selected shadow action in the challenge world;
10. ingest only its public observation/receipt;
11. encode exactly one binary native outcome for the selected temporal feature;
12. resolve the native inquiry;
13. run one more ordinary copied Core cycle;
14. require Phase42 mismatch/resumption = 0 and no Action/Planning Lab authority.

## Acceptance

- 4/4 layouts have persisted action associations.
- 4/4 reproduce exact selector output after recorder reload.
- 4/4 execute a valid public challenge command.
- 4/4 yield an evaluable one-transition native outcome and resolve the inquiry.
- 4/4 remain Phase42-clean.
- At least 1/4 is behaviorally evidence-sensitive versus the empty-association control.

Supported/falsified outcomes, selector modes, and differences from the unguided explorer are reported but are not tuned targets.

## Authority boundary

This is still shadow research.

The epistemic selector is **not** wired into live AgentCore action authority. Copied Ora owns the inquiry/evidence lifecycle, but the action-selection research process executes the selected challenge command externally.

No Phase42/43 credit, score tuning, agenda-cap changes, provider activation, Observer/UI changes, production retention, or world-mechanic changes are authorized.

If this passes, the next boundary is a **bounded action-authority proposal**: define an explicit opt-in challenge action envelope on copied state, with rollback, source identity, rate/step limits and no production activation. It should be reviewed separately before any live authority exists.
