# Whole-run composition and current evidence

The scientific ceiling remains 512 MiB concurrent tree RSS, 900 aggregate CPU
seconds, 1,500 uninterrupted wall seconds and 192 MiB output including a 1 MiB
failure/finalization reserve. Scientific execution remains disabled.

## Native entry and CPU

The supported outer entry is a prebuilt, frozen, statically linked native binary.
No Python helper remains alive. It derives one monotonic BOOTTIME origin from its
process birth, arms an absolute kernel expiry before startup/source work, and
keeps it armed through final report writes, filesystem operations and exit. A
prewritten reserved failure record survives expiry during finalization.

The entire source-audited single-thread tree is restricted to one already allowed
CPU before fork and inherits that restriction unchanged. Its prospectively fixed
internal window is 850 seconds. Aggregate scheduled CPU of the whole tree cannot
exceed elapsed time on that one CPU; this includes supervisor/controller/child
work. This avoids an unsupported multiplication of integer RLIMIT_CPU overshoot
allowances. The scientific CPU and wall ceilings are not enlarged. Individual
per-role CPU limits remain additional safeguards, not the aggregate argument.

The guarantee is the ordinary Linux kernel-backed mechanism, not a hard-real-time
or hostile/broken-kernel promise. Signal-delivery scheduling and uninterruptible
I/O limitations are disclosed. Authored tests explicitly cover a paused outer
with live descendants, paused finalization, and a blocked finalization write;
the kernel expiry kills the group and preserves the reserved terminal fallback.

## Memory and process inventory

Only the native outer (32 MiB soft AS), controller (96 MiB) and one sequential
worker/report/reconciliation child (384 MiB) coexist. Their sum is 512 MiB.
Outer/controller hard AS ceilings retain 384 MiB so the child can raise its
inherited soft ceiling. Audited supervisor paths never raise their own soft cap.
The early fork overlaps are at most 64 MiB and 224 MiB, respectively. Child hard
AS is fixed to its role. NPROC, no-thread/source checks, closed descriptors and a
sanitized environment prevent unregistered descendants in the supported model.

AS is a conservative upper bound for resident user mappings, not an RSS meter.
The native entry is static; actual Python initialization under 96 MiB is tested.
Trying to use a Python prefix under the outer's 32 MiB failed before user code,
so that prefix route is not used. The external unit-test observer is outside the
native resource unit and is not needed to launch it directly.

## Fixed output allocations

`artifact_inventory.py` reserves these logical byte maxima prospectively:

- Capsules: 128 MiB (64 × 2 MiB)
- Separate copied source inputs plus common setup snapshots: 24 MiB
- Four full D/cohort references: 2 MiB
- Saved exports: 24 MiB
- Ledger and logs: 2 MiB
- Concurrent temporary replacement peak: 3 MiB
- Reports: 6 MiB
- Manifests: 2 MiB
- Failure/finalization: 1 MiB

Total: 192 MiB. A source set has fixed Ora/world/observation reservations of
8/96/208 KiB; 64 sets occupy 19.5 MiB, with 4.5 MiB left for common snapshots.
Inputs exceeding their frozen resource slot stop the run; they are never dropped,
trimmed or resampled. Native capsule writes require an admitted slot and one
sequential 2 MiB temporary envelope. A stranded temporary ends the run. Other
atomic writes, full materialized views, raw exporter duplication and final report
serialization consume their named allocations. Unused allocations do not excuse
unregistered files. FSIZE is supplementary; inherited hard FSIZE must permit the
largest role slot before descendants lower their own cap.

The allocation algebra and bounded parent writes are tested. Actual native
transport integration must still prove that every file and temporary uses it;
those are distinct claims. The one real software fixture has its own smaller
fixed inventory and separate six-transition receipt.

## Frozen dispatch counts

The v4 schedule permits at most 384 normal capsule workers: 64 combined
create/read/reference/T1/read workers plus 320 later cold stage workers. There
are four neutral workers, 32 four-probe workers, at most one globally terminal
read-only reconciliation and one saved reporter. No retries, extra API reads,
producer preflights, reference replacements or continuation are permitted.

Source-derived whole-run caps are 64 producing constructions, 1,986 capsule
validations and 4,486 independent D reconstructions. Actual starts/exits are
tracked separately. An unexpected already-entered call is recorded as an overrun
and invalidates; it is never clipped to the cap. Pre-dispatch reservations are
the primary prevention.

## Evidence scope

Native and Python authored-fixture evidence is in the accompanying launcher
receipts. The kernel timer and inherited singleton affinity are supported by
upstream Linux man-pages for getrlimit(2), clock_gettime(2), timer_create(2),
sched_setaffinity(2) and proc_pid_stat(5). These explain the mechanisms; actual
source/role/inventory integration remains subject to exact-byte review.

The workspace advertises fsync=volatile. The API's promise is process-crash
atomicity with local fsync/locks, not machine-power-loss durability; this flag is
recorded without changing that scope. No mounts, cgroups, credentials, persistent
access or system security settings were created or changed.
