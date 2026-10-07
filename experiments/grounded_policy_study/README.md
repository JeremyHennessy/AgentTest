# Grounded policy study foundation

This is a publication of the exact source used by one completed **software
integration fixture**. It is stacked on draft #223, commit
`cd74ab1db60bf650cc6730db95a4137d578e49df`. No existing repository file is changed.
The 32-pair scientific comparison has **never run** and remains disabled.
The scientific scorer and driver are unadmitted; a known incomplete-run
ordering-classification defect is documented in the
[limits](../../docs/grounded-policy-study/LIMITS.md).

`executed_snapshot/` preserves all 59 source, test and reviewed-input files plus
their original manifest byte-for-byte. Its README and comments describe earlier
review stages; they are historical evidence. Current status and terminology are
in [the implementation notes](../../docs/grounded-policy-study/IMPLEMENTATION.md).

From the repository root, run only the authored-data checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python -B -W error::ResourceWarning -m unittest discover -s tests -p 'test_grounded_policy_study_foundation.py' -v
```

Or run the isolated entry point directly:

```sh
python -I -S -B -W error::ResourceWarning experiments/grounded_policy_study/run_zero_world_tests.py
```

These checks require Linux, Python 3.11+ and an installed C compiler with static
linking support and the usual `-s` link-time stripping flag. The wrapper creates
a disposable test-only `cc` shim that adds `-s` before the frozen builder hashes
the compiled binary. It verifies the compiled size and hash, and confirms that
a binary above the unchanged 1 MiB bound is still rejected. No frozen source,
limit or build receipt is patched. The wrapper copies only the frozen snapshot
into a temporary workspace to reproduce historical test paths. It runs authored scalar functions,
JSON fixtures, fake executives, and native resource stubs. It does not stage the
real API, completed run, operational approval receipt, or reviewed native binary.
The real fixture is not a discoverable test or CI target.

Read [verification](../../docs/grounded-policy-study/VERIFICATION.md),
[limits](../../docs/grounded-policy-study/LIMITS.md), and
[evidence provenance](../../docs/grounded-policy-study/EVIDENCE.md) before using
this material. The current-source wrapper is separate from the frozen runtime.
It grants no scientific or real-fixture activation.
