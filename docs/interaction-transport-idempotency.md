# Human interaction transport idempotency review

Status: review-only. This change does not alter ordinary autonomous heartbeats,
enable recovery transactions, or activate a new world.

## Problem

The human-interaction workflow runs on an ephemeral GitHub Actions runner. One
interaction contains two durability layers:

1. the local Core cycle and interaction writes on the runner;
2. the later git commit/push to `autonomous/growth`.

If the state push succeeds but the runner dies before posting its GitHub reply,
a rerun must not execute another Core cycle for the same user request. Local
file recovery alone cannot solve this remote acknowledgement boundary.

## Stable request identity

New workflow-triggered interactions receive a transport ID independent of
message text:

- manual workflow dispatch: `workflow:<github.run_id>`;
- owner issue comment: `issue-comment:<comment.id>`;
- owner-created one-shot issue: `issue:<issue.id>`;
- workflow-file push fallback: `push:<github.sha>`.

A rerun of the same GitHub workflow run keeps the same run ID; separate dispatch
events obtain separate IDs. Repeated identical message text is therefore not
collapsed.

The ID is persisted in the interaction record and matching journal event.
Direct interaction calls that omit a request ID preserve the old record/event
shape.

## Rerun behavior

Before starting the interaction step, the workflow searches persisted organism
interaction history for the request ID.

If it exists, the workflow reconstructs the minimum response view from persisted
state and **does not invoke** `agenttest interact`, invariant tests, or another
git push. If the current `last_interaction.json` is the same request it is
reused directly. This supports rerunning an older request even after later
interactions have replaced the latest sidecar.

If the request ID somehow reaches `interaction.interact` again, the function
fails before `AgentCore.cycle`. This is a second fail-closed boundary, not the
normal reuse path.

Multiple persisted records with the same request ID are treated as corruption
and stop the workflow.

## Reply acknowledgement

GitHub replies include a hidden marker
`<!-- agenttest-request:<request id> -->`.

Before posting, the workflow lists existing issue comments and skips the post if
that exact marker already exists. One-shot issue closing is also idempotent: an
already closed issue is not closed again.

## Limits

This prevents a second *durable* interaction after the first state push and
prevents duplicate GitHub replies for the same persisted request.

It does NOT preserve ephemeral state if the runner disappears before git push.
In that case the remote branch contains no completed interaction, so a rerun
executes the request again. Solving that requires a separate remote precommit or
checkpoint design and must be reviewed before claiming end-to-end exactly-once
interaction execution.

This change does not integrate the local exact-event recovery prototype, alter
Core cycle semantics, change cognition/provider settings, or activate world
authority.
