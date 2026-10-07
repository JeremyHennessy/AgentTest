# Elide temporary copies in private validation

Validation previously copied the entire capsule into a private prefix, replaced
six large members, and then copied that prefix again in `_stage_selection`.
The prefix is now shallow. `_stage_selection` retains its complete detached copy
before mutation or capacity-null fallback.

`encoded` now builds a fresh top-level envelope and returns the same canonical
bytes. `verify_seal` computes the same digest directly. Both read nested values;
public `seal` still returns an independent deep copy. Direct checksum validation,
source/runtime rehashing, model/semantic checks and capacity rules are unchanged.

This equivalence applies to quiescent, ordinary JSON graphs owned by the current
transaction. It is not a guarantee for concurrent mutation or custom Python
copy/iteration callbacks. `.items()` and the existing non-dict checksum guard
preserve malformed-root rejection; malformed payloads still reach hashing before
a bad-seal comparison completes.

Four focused differential checks cover exact bytes and errors, input nonmutation,
deep isolation, real accepted lifecycle/null/cancelled states, exact byte limits
and one-byte-under capacity fallback, and resealed tampering. Each source version
executes 27 validations on authored engineering inputs, with no producer,
selector, transition or API action calls. The included D2 recipe was produced by
the separately reviewed engineering component; it contains no scientific-run
data. Tests regenerate path, source, inode and dependent identities per version.

Earlier checksum-only component measurements motivated this work: D2/U0 read
CPU was 5.312 versus 4.856 seconds, and D32/U28 was 22.414 versus 19.740 seconds.
The longer component attributed 4.366 seconds to `_stage_selection` and 3.886
seconds to the validator's own remaining work. These are fixed-order profiled
engineering measurements, not study results or predicted savings for this patch.
The extra timing comparison is deferred. No full-study budget-fit or scientific
admission claim is made; default-off activation and the preserved invalid result
remain intact.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m unittest discover -s tests -p 'test_grounded_policy_v2_copy_elision.py' -v
```
