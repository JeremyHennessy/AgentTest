# Scientific implementation snapshot v3: default-off checkpoint

V3 names this corrected implementation snapshot. The preregistered study
protocol remains **V4**, with unchanged conditions, corpus, budgets and acceptance
criteria. No scientific comparison has run.

This additive source overlay is stacked on #224 at
`f67d9fe7904636949cf1c7cc29a8a4e47beccc37`. All existing snapshot, API, protocol,
workflow and compiler-wrapper files remain unchanged. Nine runtime files and six
test files compose with the immutable foundation; their bytes are preserved
exactly. The resulting runtime has 34 Python modules plus the reviewed native C.

## Narrow correction from unpublished v2

The native launcher embeds the controller through Python `-c`, where
`__package__` is None. The v2 controller's locally defined marker, failure-status
and terminal-emission helpers then attempted relative imports without package
context. Its earlier default-off review missed that entry-path defect.

Only `scientific_controller.py` changes in the v3 runtime: after installing the
pinned source loader, main binds those three helper names to functions imported
from the captured package module. Only its controller test file changes. The new
isolated `python -c` regression demonstrates both the original helper failure and
the corrected main-local binding. It never invokes real main, opens a GO receipt,
writes a marker, or imports an API/world.

The v2 package and 115-check result remain preserved. Its signoff is explicitly
superseded for operational entry correctness. The current
[default-off signoff](evidence/default-off-signoff-v3.json) and
[review](evidence/default-off-review-v3.md) bind the v3 identities; neither grants
scientific execution or activation. Earlier source corrections to chronology,
worker-completion accounting and invalid-report precedence remain unchanged.

## Fixed limits and remaining gate

Protocol V4 still fixes four layouts, 32 pairs, 64 capsules, 128 decisions and at
most 512 transitions, with no retries. Ceilings remain 900 aggregate CPU seconds,
1,500 wall seconds, 512 MiB concurrent tree memory and 192 MiB output. Native
supervision retains one CPU, its 850-second internal window and the included
1 MiB finalization reserve. No limit or acceptance criterion changes here.

All scientific admission guards remain off and the native reviewed-profile hash
remains blank. This source-only publication supplies no operational profile,
GO receipt, enabled binary or scientific result. Operational enabling and its
exact source/profile decision remain separate. Passing authored checks does not
establish scientific feasibility, predictive benefit, learning or new-world
readiness. Resource claims assume trusted source and ordinary working Linux
kernel semantics, not hard real-time behavior or survival of machine loss.

Old raw six-call evidence and historical binaries remain unavailable. The old
software fixture remains consumed despite its missing marker. See
[verification](VERIFICATION.md) and [recovery provenance](PROVENANCE.md).
