# Concurrency-group migration after obsolete interaction checkout

Status: operational workflow repair.

A human-interaction push run created from pre-blobless commit
`b9582abaa3d7d11ee883bede1d98af5575b29cb7` remained in full-blob checkout and
held the shared `agenttest-autonomous-growth` concurrency group. Subsequent
autonomous-growth dispatches could not start; GitHub retains at most the active
and latest pending run in a concurrency group, so intermediate pending
heartbeats were cancelled.

The obsolete active run is a `push` event from the workflow-source merge. Its
resolved push path sees existing interaction history and sets
`SKIP_INTERACTION=true`; all claim, Core interaction, test/persist and reply
steps are conditional on not skipping. It cannot push state when it eventually
leaves checkout.

Both current workflows therefore move together to
`agenttest-autonomous-growth-v2`. Keeping the same new group preserves
serialization between real heartbeats and future human interactions while
allowing them to proceed independently of the obsolete no-write run on the old
group.

No schedule, state, cognition, scoring, world authority or interaction semantics
change. The migration is one-time operational coordination; future group changes
must update both workflows together.
