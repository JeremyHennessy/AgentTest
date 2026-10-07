# Reuse the checksum within one capsule read

`CapsuleStore._read_locked` already verifies the checksum of its freshly parsed
private JSON object. Its confinement and pinned-identity checks only read that
object. It now passes `verify_checksum=False` to the following full validator,
avoiding the second checksum over the same unchanged state.

No cache survives the call. Every subsequent read parses and verifies its own
input. Direct `validate_capsule` calls still verify checksums by default. Source
and runtime rehashing, model and semantic validation, lifecycle checks, limits,
and validation-call accounting remain unchanged.

Four differential checks cover twelve authored rejection cases per version:
tampered seals, re-sealed confinement/identity/schema/profile failures, a fresh
second read, and the direct-validator default. They verify the same private
object and bytes at the call boundary, identical rejection behavior, unchanged
validation/source/runtime checks, and exactly one removed checksum operation.
The cold subprocesses enter no world, producer, selector, or checker functions.

Run the focused checks with the existing repository test runner:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p 'test_grounded_policy_v2_checksum_reuse.py' -v
```

Runtime savings and full-study budget fit remain unmeasured. These negative-path
checks do not cover accepted worst-case capsules or the complete process
schedule. The separately proposed budget benchmark remains on hold. This repair
does not alter or authorize repeating the preserved invalid comparison.
