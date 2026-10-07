# Heartbeat save and recovery contract

The growth Git branch remains the sole durable state owner. Transport metadata
is one current pointer at `state/heartbeat_operation.json`; old exact receipts
remain in Git history. This is an operational repair, with no change to cognitive
policy, ordinary cycle flags, inquiry budgets, or the disabled investigation gate.

## State transitions

1. **Ready → pending:** verify the exact dispatched main source and CI, then
   prepare a clean growth checkout. Freeze its existing repository observation,
   cycle timestamp, source SHA, Python implementation/version, state blob
   identities, input commit/cycle, and original workflow run ID. Publish the
   pending sidecar before Core. Claim and result commits carry the exact trailer
   `Heartbeat-Request: <request_id>`.
2. **Pending → computed locally:** only the same original workflow run may
   resume. Its code, runtime, flags and input must match. Both HEAD and a fresh
   remote fetch must equal the claim commit. Run the existing ordinary cycle
   using the frozen observation, then the unchanged proposal/diagnostic pipeline
   and required integrity/preservation checks.
3. **Computed locally → candidate:** require exactly one new cycle, its journal
   event, and an unchanged journal prefix. The completed sidecar binds the claim
   and resulting state blob identities. Commit all state once.
4. **Candidate → published:** retry only that immutable Git commit. Fresh remote
   reads after either successful or failed pushes determine completion. The
   remote must equal or descend from the candidate; an unchanged expected remote
   parent permits retry. An incompatible advancement or unreadable outcome must
   never trigger Core, rebasing, force pushing, or regeneration of a result.

The claim's immediate parent can be a local verified-source merge. The first
publisher therefore receives the fetched remote SHA from **before** that merge
as its expected parent. The result publisher receives the confirmed claim SHA.

Repeated completed IDs are resolved through their exact Git trailers and
validated historical sidecars. They never become new work when the current
pointer advances. A shallow history cannot prove an old ID absent. A new request
must equal the deterministic successor derived from the current terminal receipt
including bootstrap against the freshly fetched growth SHA.

## All writers and scheduling

Growth, interaction and reconciliation inspect pending transport metadata before
merging source or modifying state. A different writer releases the shared lane:
`writer-check` returns JSON `status=deferred`, `reason=heartbeat_pending`, and
exit status 75. The workflow exposes this only through its distinctive failed
step `Heartbeat pending: deferred writer`; network/parse failures must not use
that marker. Recovery later reruns the original deferred GitHub events. Waiting
inside the shared lane would deadlock the recovery run behind the waiting writer.

Controllers use exact request tickets and run identities, not the latest run
returned by Actions. A duplicate completed controller ticket must not enqueue
another successor. An ambiguous dispatch can redeliver the same ticket; it must
not mint another request. Pending recovery reruns the recorded original workflow
run, preserving its SHA/ref. Rerun age/attempt limits are blocked states.

An independent scheduled watchdog performs lightweight checks and is a no-op
while the matching chain is healthy. It does not execute Core or tests and does
not hold the state-writer lane. It resumes pending work, restarts a dead chain,
and replays specifically deferred writers. GitHub schedules can be delayed or
dropped; recovery depends on GitHub becoming available.

## Existing bounded investigation mode

The ordinary workflow keeps its gate false. The transport also composes with the
existing bounded claim: create the existing organism claim first, then capture
its resulting exact state in the transport sidecar, and publish both in **one**
pre-cycle commit. Both claim validators therefore see the same clean remote
HEAD. The existing bounded completion verifier runs before the transport receipt
is finalized. The existing 16-request bound, completed history, action allowances
and default-off activation remain unchanged. An older bounded pending claim
without a transport owner requires its original recovery; it is not adopted or
silently abandoned.

## CLI integration

Invoke the source-pinned helper with Python `-I -B`. All commands accept
`--root <checkout>` and emit one JSON result; blocked operations emit JSON on
stderr and exit 1.

- `inspect [--request-id ID]`: local selected branch pointer; `status` is `ready`
  or `pending`, with `operation`, `head`, `next_request_id`, and `ticket_since`.
  Requested status is `unseen`, `pending`, `completed`, or `abandoned`.
- `inspect --remote`: freshly fetch/read the growth pointer without checking it
  out. Add `--shallow` only for a current-pointer-only watchdog inspection.
- `claim --request-id ID --source-sha SHA --run-id RUN --mode ordinary`:
  `created`, `already_claimed`, or `already_completed`; returns `input_commit` and
  the required commit trailer when created. The alternative mode is
  `current-world-investigation`.
- `cycle --request-id ID --source-sha SHA --claim-commit SHA`: run the existing
  cycle only after exact remote/input validation; `computed_locally`.
- `complete --request-id ID --source-sha SHA --claim-commit SHA`: bind the checked
  result without committing or publishing; `completed_locally`.
- `publish --candidate SHA --expected-parent SHA [--attempts 4]`: reconcile and
  retry the same commit; only verified remote success returns `published`.
- `writer-check`: `ready` or the distinctive deferred result described above.

The claim imports the verified existing perception code; bounded mode also
imports its existing claim helper. Only `cycle` imports and invokes Core.

## Limits and rollback

A lost runner preserves only data successfully saved remotely. Pending intent
can resume identical pure work; it cannot recover bytes from a local candidate
that never reached remote storage. Guarantees are one accepted durable result per
request and identity-checked replay, not zero repeated transient calculations or
exactly-once external effects. No blanket artifacts are added; the observed
journal and organism together already exceeded 150 MB.

Stop new controller tickets before rollback. Resolve pending work using its
verified result or an explicitly audited abandonment after checking unchanged
input and absence of a completed result. Keep a tombstone and old Git history;
never clear pending metadata or revert organism history merely to unblock work.
The helper intentionally supplies no automatic abandonment command.

The ten-minute recovery schedule runs at minutes 7, 17, 27, 37, 47 and 57: at
most 144 short checks/day, each with a three-minute timeout (432 runner-minutes
maximum configured time). Healthy checks perform receipt/activity reads only.
Standard GitHub-hosted runners are free for public repositories under the
[current GitHub billing rules](https://docs.github.com/en/actions/concepts/billing-and-usage);
no artifacts, paid runner class or spending-limit change is added.

For the known pre-migration reconciliation run `37642389633` only, a script-level
pending check protects the old workflow after it loads growth source. Its original
triggering verify event could not be proven from API/UI metadata, so it is not
assumed to be a no-op. If it defers, recovery requires its exact source/run identity,
a bounded log containing the validated pending marker and exit 75 in the failed
step, and terminal proof for that same heartbeat. This closed compatibility entry
does not authorize replay of unrelated historical failures. The ordinary shared
writer queue continues to serialize queued reconciliation with growth.

The [fixed-window operational audit](heartbeat-reliability-audit-20261007.md)
records the population, sampling and observed failure/correlation evidence.
