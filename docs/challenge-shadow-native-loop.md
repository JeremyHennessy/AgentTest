# Challenge shadow native loop

Status: isolated research only. No live challenge-world action authority.

Production base: `bd78db8342d267822795f59a395fe5958beeed84`.

Pinned copied Ora state: `autonomous/growth@825d2c86759f5f4065807508ab7fbfe3462feb8a`, cycle 4522.

Reviewed source comes from closed PR #188:
- commit `80c0f63163d08aa2efc04ca60e1c41032ba2e839`;
- world blob `49683553596400e8c7b49b5ed5fdec5f937b7a22`;
- explorer blob `db5415b17077fdad65bf1671700f79979ff92be1`.

The normalized objective and observe/inquire integration are also copied byte-for-byte from their previously verified research versions.

## Question

Can the richer challenge world feed only its public observations/receipts through the existing recorder/integration boundary so copied Ora:

1. forms a native temporal inquiry,
2. carries that inquiry through an ordinary Core cycle,
3. receives a later genuinely new public challenge transition,
4. resolves the inquiry as supported or falsified,
5. continues ordinary operation,
6. preserves Phase42 integrity and preexisting agenda identity,

without receiving challenge-world action authority?

## Separation of responsibilities

The challenge world and frozen least-tried explorer run outside Ora.

The streaming recorder has its own small research StateStore. It retains only:
- latest public observation;
- aggregate temporal/action counts;
- recent public observation refs;
- hash-chain/source metadata.

It does **not** write every challenge observation into copied Ora state.

Only the final cumulative publication is staged into the copied Ora state through the previously verified native observe/inquire integration. That staging uses current production `AgentCore.record_native_evidence()` and `propose_native_inquiry()`.

After one ordinary copied Core cycle, the external frozen explorer continues the challenge world until the selected temporal feature is evaluable again. Exactly one new transition is encoded as native temporal outcome evidence and passed to the current native resolver.

## Four-layout protocol

Each challenge layout gets an independent copy of the same pinned live Ora state.

For each layout:
- stream 600 challenge transitions through the isolated recorder;
- select the highest eligible frozen `information_gain` temporal candidate;
- stage the publication atomically;
- require no cycle, agenda-decision, Action Lab or Planning Lab changes during staging;
- run one ordinary Core cycle with the pinned repository observation;
- require the native question to appear in ordinary agenda with an active experiment path;
- preserve all preexisting thread identities as active or archived;
- require zero Phase42 handoff/selection mismatches and no manufactured resumption;
- continue the challenge with the same frozen external explorer;
- within 96 additional public actions, capture the first transition where the selected feature is evaluable;
- record exactly one fresh binary native outcome and resolve the inquiry;
- run one more ordinary copied Core cycle;
- again require zero Phase42 mismatch/resumption and no lab action authority.

The challenge action that produces the outcome is explicitly external. It is not selected by live Ora in this experiment.

## Source identity

The recorder source ID is derived from a canonical descriptor containing exact reviewed source commit/blob IDs. The ordinary integration manifest remains `hash_chained_unsigned`: integrity is pinned, but no signed source-authentication claim is made.

## Explicit non-scope

This branch must not:
- modify `src/agenttest/**`;
- modify live state;
- merge the challenge world into production;
- grant Action Lab or Planning Lab control of challenge actions;
- count challenge evidence as Phase42/43 progress;
- change Phase42 scores or agenda capacity;
- activate external/OpenAI model providers;
- change Observer/UI;
- enable production retention/archive wiring.

If this loop passes, the next research boundary is **shadow evidence-driven action choice**: use persisted public action associations and the frozen epistemic selector to choose the next challenge action on copied/shadow state, still without live authority.
