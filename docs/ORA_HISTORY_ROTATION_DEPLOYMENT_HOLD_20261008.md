# Original Ora journal rotation — deployment hold (2026-10-08)

This is a read-only deployment handoff, **not** an installed history-rotation fix. It must not be interpreted as a deployed protection.

- Production source baseline: `main` `84b987926b214adefa387a7465d64446b801bdd4` at inspection.
- Growth branch inspected: `91a9fe7e56dce6afedcb429e56c929ce0fb49de1` (moving live-state branch; recheck before any mutation).
- `state/journal.jsonl` at inspection: 98,837,942 bytes, blob `022a1428a331942500cc73894fa2dba46eeb09b7`, approximately 6,019,658 bytes below GitHub's 100 MiB blob limit.
- Local unpublished candidate: `ora2-turn8-unpublished-custodian-package-20261008.zip` in custodian handoff attachments. Its workflow explicitly labels itself DRAFT ONLY. The candidate has not been integrated with main and its heartbeat-history reader patches remain unapplied.
- Local focused test rerun: 26 tests, one skipped. This is not full main-repository CI and does not authorize the state mutation.
- Immediate engineering dependency: review exact main source readers and scripts, apply archive-aware compatibility, integrate candidate on a separate branch, test all source/state preservation checks and exact-head CI, then merge verified code to main. Rotation must run exclusively between completed heartbeat claims on an exact verified growth parent, preserve original journal Git blob by SHA, and verify both reconstruction and successor heartbeats after deployment.
- Do not merge this documentation-only branch as a fix, dispatch the draft maintenance workflow, reset live state, delete history, or enable the separate Ora 2 pilot.


## Custodian release discipline (October 8, 2026)

- Treat a safety, permission, or CI block as an explicit unresolved deployment incident, never as a reason to declare the release complete or bypass the block.
- First recheck current main, autonomous/growth, pending heartbeat claims, exact PR head, and live journal headroom. Never use stale source/state SHAs.
- Maintain one tracked integration candidate. Add actual rotation implementation and all archive-aware reader/heartbeat/research compatibility patches before asking for merge.
- Verify exact-head repository CI, untouched historical bytes and Phase 41 commitments, lossless reconstruction, concurrency/exclusive maintenance scheduling, resumability, rollback, post-rotation real heartbeats, and research readers. No production history mutation before these gates.
- If GitHub rejects writes, capture the exact error, leave the protected branches and persistent pilot unchanged, preserve local diffs and checks, and report the blocked publication clearly. Do not route around platform security via another identity, API or privileged workflow.
- Following a verified, legitimately permitted deployment, check rotation receipts and subsequent durable heartbeat completions separately; only then mark the incident resolved. The periodic two-hour independent summary remains read-only.

## October 8 integration progress (NOT A DEPLOYMENT)

This branch now contains the staged journal-tail module, guarded rotation workflow, heartbeat claim archive reader, diagnostic/research partial-input safeguards, and preservation/regression tests. It is no longer documentation-only. Existing live `main` and moving `autonomous/growth` are unchanged by these branch commits.

The original source anchor remains main `84b987926b214adefa387a7465d64446b801bdd4` until revalidated. Exact candidate head must be read from PR #251 immediately before review/merge; do not reuse a saved SHA. The candidate's workflow can be triggered on a verified main merge and shares the existing growth concurrency group, but **it has not been executed**, and any failed terminal/quiescence/CAS gate must leave remote history unchanged.

Mandatory verified release sequence: complete all exact-head repository CI jobs (unit, baseline-owned no-regression, capability-handoff, behavioral preservation), examine full diff and code warnings, verify no accidental state changes, merge only a reviewed exact candidate head to main, observe the scheduled guarded workflow and remote archive SHA, and confirm at least one subsequent real growth heartbeat and historical-claim verification. If any check fails, preserve the negative evidence and fix on the same branch, never route around security controls.

**Release state: implementation staged, CI pending, production storage not protected.**
