# Serialize every persistent-branch writer

## Evidence and minimal correction

PR #212 moved growth and interaction into `agenttest-autonomous-growth-v2`
to escape an obsolete no-write interaction run holding the previous group.
`reconcile.yml` remained in `agenttest-autonomous-growth`, although its final
step also pushes `autonomous/growth`. The controller's reconciliation precheck
reduces overlap but is not a lock: a reconciliation can start after that check,
and a human interaction does not go through it.

This correction keeps the current group name and includes all three writers:
`growth.yml`, `interact.yml`, and `reconcile.yml`. No writer waits for another
writer while holding the shared group. The dispatching controller keeps its
separate existing group; moving it into the writer group would deadlock its
wait for growth. No controller, event trigger, schedule or domain-code change
is included.

Reconciliation also adopts the existing blobless/full-history checkout used
by the other writers (`filter: blob:none`, `fetch-depth: 0`). This preserves
history/merge semantics and avoids fetching all historical state blobs while
holding the shared writer lane.

## Pending runs must not replace each other

`cancel-in-progress: false` prevents cancellation of a running writer but does
not by itself retain multiple pending requests. The default queue has only one
pending slot. All three workflows therefore explicitly set `queue: max`.
GitHub documents a limit of 100 pending runs and queue order by arrival at the
concurrency group, not guaranteed dispatch order. Overflow still cancels new
arrivals. This is bounded hosted queuing, not an exactly-once or unlimited
service. Existing request identities and state/append semantics are unchanged.

References, verified October 7, 2026:
- [GitHub concurrency control and queue semantics](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)

## Migration and verification

Existing runs keep the workflow configuration they started with. Do not cancel
or manually duplicate them for this repair. Before merging, inspect the old
reconciliation lane and let any old configuration capable of writing state
drain. After merge, inspect naturally triggered reconciliation and the next
ordinary growth run, including exact workflow-source SHAs, successful state
persistence and no simultaneous writer step. Do not claim scheduler behavior
was proven by a local static test.

Local regression checks discover every workflow that pushes the persistent
branch, require identical shared group/queue/non-cancellation settings, retain
full-history blobless checkout, and ensure controller isolation and the verified-
main reconciliation guard. Current hosted exact-head CI and ordinary post-merge
runs are separate verification gates. No artificial simultaneous dispatches
are needed.

This addresses a writer-coordination gap; it does not implement transactions,
make journal append idempotent, protect against external manual writers, or
activate any new world. Lossless journal rotation must remain separate until
all readers and writers have a tested contract.
