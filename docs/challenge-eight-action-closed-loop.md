# Eight-action copied challenge loop

Status: research only. Live Ora still has no challenge-world action authority.

Production base: `73d4765322efd8c7b87ed8c94bdca8bb81098d7a`.

Pinned copied state: `autonomous/growth@39b5643d66954d415ea8f1f88b0252df51ab6f04`, cycle 4570.

## Purpose

PR #193 proved one restart-safe, evidence-driven challenge action can be authorized and resolved under a strict capability boundary.

This experiment tests continuity rather than increasing environmental complexity.

Each of four mirrored layouts gets an executor budget of exactly **8 actions**. Every action must be backed by a newly staged native inquiry and a newly issued single-use capability.

## Closed-loop sequence

For each action:

1. reload the durable public recorder;
2. require recorder and executor to show the same current public observation;
3. create a cumulative native publication from current public evidence;
4. stage a **new** native inquiry in copied Ora;
5. run one ordinary copied Ora cycle;
6. require the current native experiment to remain `awaiting_native_evidence`;
7. reload the executor;
8. recompute the evidence-driven selector from persisted public associations;
9. issue one capability bound to that experiment, observation, evidence chain and command;
10. restart the executor;
11. consume that capability exactly once;
12. restart again and require replay rejection without file mutation;
13. ingest the resulting public receipt/observation;
14. require the recorder evidence-chain hash to advance;
15. encode exactly one fresh binary native outcome;
16. resolve the native inquiry before the next action can be authorized.

After action 8, a ninth issuance must fail with exact budget exhaustion. One final ordinary copied Ora cycle verifies continuity after the last resolution.

## Additional multi-action safety rule

A native experiment may receive **at most one** challenge capability.

This prevents a multi-action budget from accidentally authorizing several actions under one stale inquiry. The next action therefore requires a fresh native experiment even if the question text/feature repeats.

## Acceptance

Across all four layouts:

- exactly 8 authorized actions/layout;
- exactly 8 fresh native experiments/layout;
- exactly 8 fresh native outcome evidence episodes/layout;
- exactly 8 unique pre-action recorder chains/layout;
- capability IDs/ordinals advance monotonically 1..8;
- executor restarts before every real execution;
- replay rejected after every consumed action;
- ninth issuance rejected by exact budget;
- every native inquiry resolves supported or falsified;
- every ordinary Ora cycle has no challenge Action Lab/Planning Lab authority;
- Phase42 mismatch/resumption remains zero throughout;
- pinned source state remains byte-identical.

Supported/falsified counts, selector modes and difference from the unguided command are measurements, not tuned targets.

## Explicit limits

This still does not:
- modify `src/agenttest/**`;
- modify live Ora state;
- grant live challenge-world action authority;
- count challenge evidence toward Phase42/43;
- use raw challenge traces in the selector;
- change Phase42 scoring or agenda capacity;
- enable external/OpenAI model providers;
- change Observer/UI;
- enable production retention/archive wiring.

If this passes, the next checkpoint is **not** “more actions automatically.” The correct next decision is whether the 8-action trace shows coherent evidence-driven adaptation over time. Only then should a proposal consider a limited live/shadow bridge or a more open-ended world.
