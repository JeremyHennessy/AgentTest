# Separately versioned observed-effect admission

The frozen `b189d656` context-novelty preflight remains a valid negative result.
It promoted 32 additional contexts but changed no retained model structure or
action availability, so it correctly prepared no new case. Its report, original
case and recipe are not rewritten.

This follow-on is an explicit representation-admission change:
`current-world-investigation-v3` uses `observed-effect-revision-v1`. It preserves
the previous `observed-transition-revision-v1` signature rule only as the narrow
reader needed to verify historical context-revision records and cases.

The new admission unit is `(action, observed displacement)`, with displacement
derived directly from the actual before/after positions. In source order, it
promotes the first row for each effect absent from original discovery and earlier
additions. The entire row, context, ID and source-body references are preserved.
Familiar displacement at a different position no longer spends a promotion slot.
Every genuinely new effect qualifies, including contradictory nonzero effects;
the unchanged generator may correctly reject those as outside its model class.

This directly matches the generator's existing requirement for zero displacement
and exactly one nonzero displacement per action. It does not invent a missing
contrast, assume one exists in later history, seek a desired direction, or keep
searching until a choice appears. It cannot generally discover new contextual
conditions once all effect types are represented, and it does not guarantee a
new retained model or selectable inquiry.

All other contracts remain unchanged: at most 32 additions, 64 discovery rows,
one revision, the original two-case/two-action limits, 8,192 observed rows,
4 MiB checkpoint, 256-digit rational bound, model grammar, score and threshold.
The original null still occupies one case slot, leaving at most one additional
case/action. Pending authority remains bound to execution content and cannot be
reinterpreted under changed code. A prior installed context revision would remain
immutable and would not be reset or automatically replaced.

Each new revision uses all history outside its own discovery-ID set as posterior
evidence. Promoted rows are excluded from that evidence; original cases resolve
their original cohort/partition. The read-only preflight reports both candidate
and active revision recipe versions, old-record preservation, full partition IDs,
model changes, selected/null/blocked, byte/numeric limits and claim headroom.

This change does not activate the workflow or modify live state. One pinned
full-history preflight and exact-head CI precede any separately reviewed rollout.
The failed context-novelty report remains preserved alongside that new result.

The matched source is the complete post-rollback cycle-6,521 state at
`72c234c2aeef546e25689a86bbf8c0911595ab02`, with raw SHA256
`5efeed6d72824ef6b5e463854b2217b1a383eb5f3db35fce7f0571ea02b286b6`.
The workflow pins Python 3.12.14, matching the recorded first admission, because
floating 3.12 selected different patch versions across actual runners. Historical
case runtime bindings remain untouched. The [earlier read-only run and attached artifact](https://github.com/JeremyHennessy/AgentTest/actions/runs/37641510899)
remain attributable to their original candidate and are not evidence for this one.
