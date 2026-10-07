# Implementation-v3 verification, unchanged protocol V4

On 2026-10-07, the exact implementation-v3 composition passed all **116** selected
authored checks in 11.557 seconds. The outer one-test wrapper took 12.062 seconds.
There were no failures, errors or skips, and resource warnings were errors.
[The full log](evidence/publication-zero-world-tests-v3.log) and
[verification receipt](evidence/publication-verification-v3.json) bind this fresh
result to the current source composition.

| Selected scope | Checks |
| --- | ---: |
| Scientific controller, including the new Python `-c` regression | 8 |
| Scientific transport | 16 |
| Scientific reporter | 20 |
| Driver | 2 |
| Scorer | 44 |
| Native projection against the corrected scorer | 18 |
| Saved-report boundary against the corrected scorer | 6 |
| Added native launcher checks | 2 |

The no-argument publication runner's interface is unchanged. It verifies both
source layers and all 68 composed files before loading the selected tests, and
rechecks staged/published bytes afterward. Runtime/test overlay bytes remain
exact. It loads #224's pinned compiler helper for definitions only, retaining the
same test-only `-s` behavior without invoking its 150-test suite. No binary size
bound, source guard or protocol constraint is changed.

## Entry regression and native test boundary

The added test starts a fresh isolated `python -c` child with `__package__` None.
It captures the controller definitions, omitting only automatic main invocation,
and demonstrates the old local helpers' relative-import failures. It then uses
main's exact local import statement to bind the helpers to the pinned package
and verifies successful authored marker-refusal, invalid classification and
terminal-event behavior. Real main is not invoked; a sentinel stops before any
GO receipt or marker I/O. No API or world imports occur.

The two C checks compile the authored setup and disabled scientific binding,
verify the latter's metadata and refusal, and compile/run a separate pure receipt
helper harness with its entry point substituted. They never invoke the scientific
native role. Transport subprocesses are authored scalar/JSON peers, not real
API workers or world streams. Actual API and world calls are zero, with zero
forbidden import attempts or loaded modules. No consumed fixture is rerun.

The full 150-test foundation suite, other native launcher modes, baseline/full
repository tests and any scientific comparison were excluded. The affected
projection/report-boundary checks are retained because they exercise the changed
scorer; this is not a second complete foundation suite.

The old pre-loss 113-check completion remains unknown. The separately recovered
113-check result and unpublished v2 115-check result are historical evidence.
V2's signoff is superseded for operational entry correctness; the fresh v3 run
covers the selected suite plus its new regression. The protocol remains V4 and
no scientific usefulness, feasibility or readiness result follows from these
software counts.

No GitHub publication or exact-head CI for this slice was performed locally.
Existing #224 at `f67d9fe` had passed its automatic CI. The new slice still needs
its own remote verification and grants no operational enabling or execution.
