# Remote pre-cycle interaction claim

Status: review-only, stacked on the stable transport identity gate.

## Why another boundary exists

A GitHub Actions runner can disappear before the final interaction commit is
pushed to `autonomous/growth`. Local exact-event recovery files disappear with
that runner, so local transaction recovery cannot make the request itself
durable.

The interaction workflow already uses the same repository-wide concurrency group
as autonomous growth. This review adds a small remote claim before executing a
new interaction.

## Claim location

The claim is stored inside the existing tracked
`state/last_interaction.json` sidecar under `pending_request`.

No new state path is introduced. Ora's repository baseline fingerprint excludes
the contents of `state/**`, while its comparable tracked-file count therefore
also remains unchanged.

The prior completed interaction fields remain intact while the pending claim is
present, so the Observer can continue rendering the previous completed response.

Claim fields:
- version;
- stable transport request ID;
- SHA-256 of the exact authorized message;
- GitHub event name.

The message itself is not duplicated into the claim.

## Remote sequence

For a new request with no completed matching interaction:

1. resolve stable request identity;
2. create or verify the pending sidecar claim;
3. commit and push that state-only claim to `autonomous/growth`;
4. run the normal evidence-linked interaction locally;
5. replace `last_interaction.json` with the completed interaction output;
6. verify tests/preservation;
7. commit and push all resulting state, thereby replacing the pending sidecar;
8. post the deduplicated GitHub reply.

If the runner dies after step 3 but before step 7, a rerun sees the same remote
claim and may execute the request again from the last durable organism state.
Any prior ephemeral cycle is lost with the runner, so only one result can become
durable.

If step 7 succeeded, the persisted interaction request ID causes the rerun to
reuse that interaction instead of executing Core again.

## Conflict behavior

Reusing the same request ID with different message bytes fails. A different
request encountered while another claim is pending also fails. The concurrency
group should prevent ordinary overlap; these checks protect corrupted or manual
states.

If there is no prior `last_interaction.json`, no claim file is created. This
preserves the repository sensor's tracked-path count at the cost of leaving the
very first-ever interaction without this pre-push claim. Current Ora already
has a tracked last-interaction sidecar; this fallback is retained for fresh
installations rather than fabricating a new state path.

## Limits

This is not exactly-once computation. A runner can perform an ephemeral Core
cycle, die before the final push, and cause the rerun to recompute from the last
durable state. The claim guarantees request identity and makes the ambiguity
visible; it does not preserve unpushed RAM/files.

No cognition, planning authority, score, world, organism schema or heartbeat
behavior is changed by the claim itself.
