# Copied inquiry executive: bounded transaction implementation

Date: 2026-10-07. Default off. Research-only, beside the unchanged production cycle.

This package implements ownership and durable state transitions for the existing
pure Challenge simulator. It does not establish learning, useful endogenous
inquiries, transferable beliefs, causal resumption, long-history persistence, or
live activation. It is not an external-side-effect executor.

The adjacent design and acceptance documents are the original reviewed, dated
contracts, preserved byte-for-byte. Their planned-test wording is historical;
actual results and remaining gates belong in `VERIFICATION.md`.

## Surface

`experiments/inquiry_executive/` contains only:

- `__init__.py`: import-first source pinning and a scoped source-only loader.
- `contracts.py`: canonical JSON, strict envelopes, bounded fixed-world schema,
  code manifest, limits, and conservative completion-size bounds.
- `store.py`: stable POSIX process lock, no-follow paths, expected identities,
  complete atomic replacement, file fsync, and directory fsync.
- `bridge.py`: a deep-copy in-memory store and one unchanged ordinary Core cycle.
- `executive.py`: passive admission, selection/precommit, execute, interpretation,
  full lineage, and revalidation.
- `synthetic.py`: explicitly authored tiny transaction-control fixtures.

There is no production import, workflow change, runtime selection-override
argument, command callback, shell/network target, provider, or new world.

## Required execution boundary

Use a fresh interpreter with bytecode writes disabled (`python -B` or
`PYTHONDONTWRITEBYTECODE=1`). Import `inquiry_executive` before any `agenttest` or
Challenge adapter module. A warm module namespace is rejected rather than
certified from the current files. The loader compiles captured source bytes
directly and ignores existing dependency `.pyc` files. An existing executive
bootstrap `__init__` bytecode cache is rejected by the pinned contract gate;
no claim is made for arbitrary warm or externally monkeypatched Python state.

All loaded source files must remain unchanged for the entire run, including
restarts. Source hashes cover every production Python module, the seven existing
adapter dependencies, and the new package. Hashes are consistency checks, not
signatures or protection from a malicious local writer. The filesystem and
interpreter are trusted. Whole-capsule malicious rollback is outside this proof.

Creation requires three explicit, distinct, unaliased copied JSON files:

- `ora`: the complete copied current-schema Ora snapshot.
- `world`: the existing fixed Challenge world, including its full receipt history.
- `observations`: the complete adjacent public prefix, each entry containing
  `observation` and `receipt` (the initial receipt is null).

The final public observation must match the copied world's public sensor. World
cycle must equal receipt-history length. Original files stay read-only and their
path, inode, size, and SHA-256 are rechecked on every capsule validation. Missing
or mismatched inputs fail closed. A new named capsule lives directly inside an
explicit research directory; live/default locations and path aliases are refused.
The lock sidecar contains no authoritative state and is never replaced. An
orphaned creation lock is safely reused under the same process lock.

`InquiryExecutive.create(..., enabled=True)` creates the capsule. Reopening
requires the same explicit research path and `enabled=True`; it never creates
missing state. The four mutations are `admit`, `select_next`, `execute`, and
`recover_or_interpret`; `read` has no persistent effects. Selection/admission and
unconsumed execution compare an expected revision. A committed identical
attempt retry returns the stored complete outcome after full validation even if
its old T1 revision is supplied.

Admission accepts only existing question/experiment IDs, 2–8 bounded declarative
hypotheses, and optionally the original 1-based frame sequence. The original
recorder publication and native grounding are reconstructed from that exact
retained prefix. Later actions do not require today's publication candidate ID
to equal the original. Current public feature availability is still required.
This first slice does not implement hypothesis-set extension or meaning
migration; new versions/linked successors remain a separately reviewed extension.

## One owned transition, three durable stages

T1 stores full pre/post Core state, actual cycle result/event, bounded candidate
summary disclosure, actual question/thread/routing, and zero or one fresh frozen
attempt. `observation=None`; all provider, lab, copied-public/frontier/dispatch
paths and both counterfactual overrides are off. Normal no-current-prediction
resumption correction remains. Planning actuation is explicitly deferred and
repository observation explicitly omitted; this is a copied experimental
treatment, not equivalence to planning-enabled legacy cycles.

T2 validates the selected owner, source/feature, public frame, code, world,
command, budget, and belief lineage. It computes one pure simulator transition
locally and atomically stores the world, budget consumption, complete receipt,
public observation, recorder, and outcome. Blocked movement consumes one action.

T3 evaluates the frozen prediction against that saved outcome and appends one
canonical case-local belief record. Missing/occluded evidence is unevaluable.
Agreeing alternatives stay undiscriminated. Interpretation cannot call the
world; changing the rule version cannot spend the same outcome again. A committed
uninterpreted result blocks new admission/selection until recovery completes.

New selection or admission cancels prepared authority in the same commit.
Suspension is tracked separately from evidence. Returning to an inquiry requires
a new actual decision and new attempt. No available runner-up replaces a winner.

## Capacity and durability

Synthetic defaults are 2 MiB / 8 decisions / 4 actions, with hard maxima
16 MiB / 16 decisions / 8 actions. Every committed selection, including truthful
nulls, counts. Reaching either budget stops new work; existing T2/T3 work can
finish. Limits are immutable across restarts. The separately declared
preserved-input profile is at most 256 MiB / 1 decision / 1 action and requires
the exact input hash. No such preserved-input run has been performed here.

Every candidate's complete canonical bytes, seal, and newline are sized before
write. T1 holds 1,048,576 bytes for completion. New frames, receipts, and belief
records are capped at 65,536 bytes. Both authoritative recorder copies are each
capped at 131,072 bytes. Fixed world nonhistory structure is capped at 8,192 bytes.

The conservative T2 growth envelope is 634,880 bytes: full outcome charged at
three 64 KiB records plus 16 KiB metadata, one 64 KiB frame, both 128 KiB recorder
copies, one 64 KiB world receipt, 8 KiB world structural change, 16 KiB event/attempt
changes, and 4 KiB seal/counter overhead. The T3 bound is 81,920 bytes. The T2
commit retains 131,072 bytes for T3; thus even T2's conservative maximum plus
its remaining reserve is below the original 1 MiB. Runtime record caps and
exact serialized growth checks enforce these limits. No transition preview is
used to size a prediction or reservation.

Intervening commits cannot spend outstanding capacity. Prepared cancellation
releases the reservation atomically; canonical interpretation releases the T3
remainder. A candidate that fails any bound leaves authoritative bytes unchanged.
The tests construct maximal independent serialized size envelopes (deliberately
larger than simultaneously reachable fixed-world outputs), as well as oversize
transition rejection with unchanged world.

A file is flushed/fsynced, atomically replaced, and followed by directory fsync.
The stable lock is process-level. Directory and lock identity are rechecked
before replacement. A post-replace durability error raises `CommitUncertain`:
reopen/re-read authoritative state before deciding what happened. Never blindly
replay. Stray temporary files are not recovery inputs. These are POSIX filesystem
checks on the test environment, not a universal power-loss durability guarantee.

## Ordinary-selector limitation deliberately preserved

The tiny real-selector positive is an authored valid state, not a natural Ora
result. Closed legacy templates and prior selection counters are disclosed.
Three real actions can retain one original source binding across fresh processes.

A second fixture has two genuinely different original source publications.
Unchanged Core can select A, then B, then A. B's returned experiment is generic
instead of its admitted native experiment; B is mapped, but receives no action.
A's successful north movement can occlude its selected entity, giving an
unevaluable interpretation and later availability deferrals. These are preserved
results. They do not establish real-selector A→B→A two-owner action switching.
An explicitly injected routing double tests cancellation machinery separately;
it is not evidence that ordinary B ownership works.
