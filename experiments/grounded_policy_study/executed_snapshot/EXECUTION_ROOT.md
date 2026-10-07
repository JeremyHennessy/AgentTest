# Execution-root and publication contract

The source package can be added beside the frozen API, for example as
`experiments/grounded_policy_study/`, without modifying any file in the API's
46-file pinned closure. The final placement is explicit in the run manifest;
imports must come from captured source bytes, not ambient PYTHONPATH or bytecode.

Two roots are supplied to `capture_execution_root(api_root, study_root)`:

- `api_root`: repository root containing the unchanged #223 source.
- `study_root`: this deliverable directory, containing `ora_study/` and
  `reviewed-inputs/`.

All eight required protocol/design/review/API snapshot inputs are copied
byte-for-byte into `reviewed-inputs/`, with original relative paths and hashes in
its manifest. The exact accepted v4 protocol and signoff are included. They are
read-only execution inputs and need not depend on an untracked local sibling.
The older `freeze.capture(workspace_root)` function is a developer-only check
against the investigation workspace's `policy-work/`, `policy-results/` and
original review directories. It is not the portable execution entrypoint.

The API runtime manifest intentionally pins the approved interpreter binary,
installed numerical source paths/bytes and Decimal runtime. Moving to another
runtime requires a prospective review/freeze before scientific data; packaging
must not silently update those fingerprints to whatever is installed.

A native launcher build is a pre-run software artifact. Its source, compiler and
binary must be frozen before execution; compiling a fresh arbitrary launcher
inside a scientific run is not an admission shortcut. Current native launcher
binaries/logs are separate software-test evidence in `policy-study-results/`.
The source package contains the C source and bounded build helper, not a claim
that those transient build paths are a portable scientific executable.

No credentials, live state, scientific outcome data or hidden external files are
required by the source package. A scientific run needs a new named output root
with the declared artifact inventory and no preexisting contents. Failure never
selects a new output path automatically. Actual scientific activation remains
disabled in the driver, cold API worker and neutral/probe worker.
