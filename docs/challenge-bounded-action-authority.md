# Bounded challenge action authority

Status: copied-state research only. No live environmental action authority.

Production base: `73d4765322efd8c7b87ed8c94bdca8bb81098d7a`.

Pinned copied Ora state: `autonomous/growth@39b5643d66954d415ea8f1f88b0252df51ab6f04`, cycle 4570.

## Purpose

PR #192 proved that persisted public action evidence changes the next shadow action in a reproducible way. This experiment adds the smallest possible authority boundary: exactly one challenge-world transition may be caused by that evidence-driven selection.

The authority gate is still outside live Ora and operates only on copied Ora state plus a separate research executor.

## Issuance contract

A capability is issued only when all of the following hold:

- the copied Ora experiment exists;
- it is still `proposed`;
- it is still `awaiting_native_evidence`;
- it carries a temporal native inquiry;
- the executor's current public observation exactly equals the recorder's persisted latest public observation;
- recorder source ID and reviewed source descriptor match the pinned challenge source;
- the command is recomputed inside the authority layer using the frozen `public-falsification-oriented-v1` selector;
- the selected command is present in the current public command set;
- the single-action budget is not exhausted;
- no prior issued capability remains unconsumed.

The token binds:

- reviewed source identity;
- world version;
- native experiment/question/candidate;
- selected feature/relation;
- exact observation ID/cycle/hash;
- recorder evidence-chain hash;
- selector policy and full selection hash;
- exact public command and command hash;
- budget ordinal.

## Execution contract

The executor owns one shadow-world file containing both world state and capability ledger.

Execution fails closed when:

- the capability is unknown;
- it was already consumed;
- token fields were modified;
- source/world identity differs;
- the observation ID/cycle/hash is stale;
- the command is no longer publicly available;
- the action budget is exhausted.

On success, challenge transition + capability consumption + updated shadow world are saved atomically in the same file.

This is an at-most-once local executor. It does not claim distributed-system exactly-once semantics or adversarial cryptographic security.

## Four-layout protocol

Each mirrored challenge layout gets an independent copy of the pinned Ora state.

1. stream 600 reviewed challenge transitions into the durable public recorder;
2. stage the same native inquiry used in #191/#192;
3. run one ordinary copied Ora cycle and require readiness preservation;
4. create a one-action executor from the exact checkpoint world;
5. issue a capability by recomputing the evidence-driven selector;
6. on cloned executor files, require rejection of:
   - mutated command;
   - source mismatch;
   - stale observation;
   - restart replay;
7. restart the real executor and execute exactly once;
8. restart and require replay rejection without state change;
9. require second issuance to fail because the one-action budget is exhausted;
10. ingest only the public receipt/observation;
11. encode exactly one fresh native outcome and resolve the inquiry;
12. run one more ordinary copied Ora cycle;
13. require Phase42 mismatch/resumption zero and no Action/Planning Lab authority.

## Non-scope

This branch does not:

- modify `src/agenttest/**`;
- modify live state;
- give live Ora challenge authority;
- let arbitrary Core text become an action;
- use Action Lab or Planning Lab as a shortcut;
- change Phase42/43 scoring or credit;
- change agenda capacity;
- enable external/OpenAI model providers;
- change Observer/UI;
- enable retention/archive production wiring.

If all four layouts pass, the next experiment may increase the copied executor budget to a fixed **8 actions** and require repeated:

`observe → native inquiry → evidence-driven select → issue → act → evidence → resolve`

with a fresh capability on every step.
