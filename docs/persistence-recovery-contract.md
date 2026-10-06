# Exact-event recovery: copy-only implementation contract

Status: isolated prototype, not production recovery. No live writer imports it.
No runtime integration, default-store access, automatic activation, workflow
change, historical repair, state rollback, or new-world authority is included.

## Preserved identities and local limits

Production baseline: `8f90f8b6157c88bc81a014cbeba668155859df3a`, tree
`658d355163fc2e87fd2a40c3c65cac6a0374aa59`.
Characterization checkpoint: PR204, `789037fa7eb32ed72077836dc1cad0a7500e5c77`,
tree `c9a745b2018723d60921ade2b0207afe51ab7e5c`. Its original tests remain unchanged.
This follow-up adds an independent standard-library script, tests, and this
contract on that checkpoint. Existing runtime files are not changed.

Local Git clone failed at DNS resolution, before authentication or download.
No credential was sought, no denied publication route was retried, and no full
current-main restoration is claimed. Local prototype tests need no AgentCore
or retained V4 implementation; hosted exact-head CI supplies whole-tree
compatibility evidence. The prior characterization archive remains evidence,
not a substitute implementation of current main.

## Scope and API

`RecoverySandbox.create(absent_directory, snapshot_bytes, journal_bytes,
copied_only=True)` copies caller-supplied bytes into new sandbox-only filenames.
An existing destination is rejected. Opening requires a matching absolute-path
copy marker, POSIX support, and explicit `copied_only=True`. Aliased/symlinked
roots and nonregular or hardlinked files reject. The marker prevents accidental
use, not hostile forgery; this is not a security capability or production fence.
No source file is moved. No source-path API, CLI, Core import or network exists.

A writer supplies an operation identity, expected raw state AND journal hashes,
exact next-state bytes, and either one exact newline-framed event or None.
None explicitly represents a legitimate state-only operation; no synthetic event
is invented for it. Stable operation identities belong to storage metadata,
not Ora's inquiry, episode, reflection, or milestone ledgers.

`read()` and a new `commit()` reject a pending transaction. `recover()` must run
explicitly before any future writer loads state or takes a cache shortcut.
Recovery never reruns an experiment, decision, clock, or event constructor.
An acknowledged request replay checks the full original request identity and
returns `already_committed`, even after later operations, without rolling state
back. Reusing that identity with different bytes fails closed.

## Commit and restart state machine

1. Under a nonblocking cooperative file lock, validate both predecessor hashes,
   valid snapshot JSON, and every existing journal record including framing.
2. Write and synchronize the exact prepared snapshot. Then publish a checksummed
   intent containing its hash, predecessor hash, journal-prefix length/hash,
   operation identity, and the exact event bytes. Intent publication is the
   roll-forward decision; orphan temporary files before it are not promoted.
3. Validate the intent, prepared bytes, current state, prefix, possible tail, and
   any terminal receipt BEFORE associated state/journal mutation. An advanced,
   missing, or corrupt snapshot is not replaced with an older or fresh one.
4. Replace the snapshot with the exact prepared target when needed. Synchronize
   the snapshot and containing directory, including on restart after replacement.
5. The journal suffix must be an exact byte prefix of the retained event. Append
   ONLY its missing suffix and synchronize. This also covers interruption before
   the final newline or inside UTF-8. Never truncate, rewrite, normalize, or
   discard prior journal bytes. A foreign/unowned tail stops recovery.
6. Publish and synchronize the terminal operation receipt, remove and synchronize
   the intent, then remove the temporary prepared payload. Repeated restarts
   after receipt publication do not append the event again.

A terminal receipt contradicting the state or event tail stops recovery rather
than silently replaying an already acknowledged operation. If original exact
intent is absent, this implementation cannot infer a missing historical event.
A valid JSON state/journal pair is not proof that all historical events exist.

The prototype uses raw writes with short-write handling, fsync, same-directory
replacement, directory fsync and a lock held through the transaction. Advisory
locking covers cooperating prototype writers only. It does not fence today's
live writers, hostile actors, path-replacement races or other machines.

## Test evidence (counts must not be called live learning)

The focused suite has 28 unittest methods, including table-driven cases:
- 20 exception interruption boundaries;
- 20 child-process SIGKILL points during commit;
- 12 child-process SIGKILL points during recovery itself;
- every byte boundary of one retained UTF-8 event, including final newline;
- several sequential interruptions of a single recovery;
- short/zero writes and fsync failure after event bytes have been written;
- exact original prefix, snapshot, and event-byte equality;
- repeated request after later commits, conflicting identities, stale state or
  journal hashes, legitimate state-only updates, distinct same-cycle events;
- malformed/resealed intents, changed prefix, corrupt or missing files,
  mismatching tails, copied-store guards, and cooperative-lock contention.

Subprocesses use synthetic temporary files only. SIGKILL demonstrates process
interruption with the same running OS; it does NOT simulate power loss, disk
cache loss/reordering, torn sectors, network filesystems, or hardware durability.
No Core.cycle, completed research study, live memory, new source observation,
attention score, or world action is used by the added tests. Original PR204
characterization still describes the unmodified live implementation.

## Mandatory writer integration map (NOT implemented by this prototype)

| Writer family | Required integration before any live proposal |
| --- | --- |
| Core cycle and outcome operations | Prepare exact post-operation state/event once; recover before loading state; no repeated semantic computation during recovery |
| Human interaction | Preserve input/output IDs and exact original event; prevent retry from producing a second interaction |
| CLI proposal/review operations | Classify paired versus intentionally state-only saves; preserve cached-result semantics and event-time identity |
| Verified-change reconciliation | Keep existing authority checks; persist its exact event only after they pass; blocked workflow scope remains blocked |
| Experiment-design diagnostic | Recover before context-hash lookup; route its direct state/event pair through the common boundary without altering evaluation |
| Blocked-attention diagnostic | Same recovery-before-cache requirement; preserve diagnostic IDs, evaluation and source-mutation claims |
| Opt-in native state-only APIs | Represent the absence of a journal event explicitly; keep all enable/persist defaults unchanged |

This table is an implementation checklist, not a claim those writers are wired.
No partial StateStore-only rollout is proposed. Reader behavior must also be
reviewed: today's Observer does not honor the new sandbox lock/intent and this
prototype does not provide atomic reads across two files for arbitrary readers.

## Remaining release gates

Define stable per-writer retry identity and commit acknowledgement semantics.
Test actual writer adapters and cached paths, direct diagnostic compatibility,
ordinary results/IDs/bytes, and restart-before-new-cycle behavior. The API alone
cannot make high-level retries idempotent if callers generate new identities.

Account for environment restart: local pending files are not guaranteed to
survive a fresh GitHub Actions runner. The existing git-push checkpoint is a
separate persistence boundary. No workflow, remote transaction transport or
permission change is included, and no remote recovery is claimed.

Measure full-size copied-state/journal overhead before choosing production use.
This prototype scans the complete journal, retains a full prepared snapshot,
and keeps per-operation receipts; it is intentionally not optimized or a
scalability result. Define retention without deleting scientific history.

A code rollback must first settle or explicitly quarantine pending transactions;
old writers ignore these sidecars and must not simply resume while one exists.
No automatic downgrade or memory rollback is implemented. Repair historical
unowned damage only with separately verified original evidence, never guesses.

Keep the independently found compact-formatting regression separate. This work
does not change the diagnostic scripts' pretty-print behavior. Observer and
capability/world activation remain later independent work.

## Filesystem references used for this contract

Python 3.12 os.fsync and os.replace documentation: https://docs.python.org/3.12/library/os.html
Linux fsync(2), including explicit directory synchronization: https://man7.org/linux/man-pages/man2/fsync.2.html
These describe mechanisms, not certification of this application or storage stack.

Run focused checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p 'test_persistence_recovery_prototype.py' -v
```
