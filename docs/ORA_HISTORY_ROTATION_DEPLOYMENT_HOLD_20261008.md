# Original Ora journal rotation — deployment hold (2026-10-08)

This is a read-only deployment handoff, **not** an installed history-rotation fix. It must not be interpreted as a deployed protection.

- Production source baseline: `main` `84b987926b214adefa387a7465d64446b801bdd4` at inspection.
- Growth branch inspected: `91a9fe7e56dce6afedcb429e56c929ce0fb49de1` (moving live-state branch; recheck before any mutation).
- `state/journal.jsonl` at inspection: 98,837,942 bytes, blob `022a1428a331942500cc73894fa2dba46eeb09b7`, approximately 6,019,658 bytes below GitHub's 100 MiB blob limit.
- Local unpublished candidate: `ora2-turn8-unpublished-custodian-package-20261008.zip` in custodian handoff attachments. Its workflow explicitly labels itself DRAFT ONLY. The candidate has not been integrated with main and its heartbeat-history reader patches remain unapplied.
- Local focused test rerun: 26 tests, one skipped. This is not full main-repository CI and does not authorize the state mutation.
- Immediate engineering dependency: review exact main source readers and scripts, apply archive-aware compatibility, integrate candidate on a separate branch, test all source/state preservation checks and exact-head CI, then merge verified code to main. Rotation must run exclusively between completed heartbeat claims on an exact verified growth parent, preserve original journal Git blob by SHA, and verify both reconstruction and successor heartbeats after deployment.
- Do not merge this documentation-only branch as a fix, dispatch the draft maintenance workflow, reset live state, delete history, or enable the separate Ora 2 pilot.
