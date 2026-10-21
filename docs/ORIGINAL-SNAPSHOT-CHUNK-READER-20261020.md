# Original Ora: staged chunked snapshot reader — no production format switch

Baseline exact main: `09abd817e71c097190546f872bb73ab31e18c7f7`. Source-gated original growth claim remains `584e861...` at cycle 9904. Trial #272 measured 6,005 KiB Git-pack space for stable 32 MiB raw chunks versus 9,129 KiB for gzip across **one actual copied native cycle**, using original ~105 MB raw state. The comparison is not a long-term repository growth bound.

This branch adds a **reader only** for a new strict envelope `ora-original-raw-chunks-v1`; original raw JSON and existing gzip format remain unchanged. Deterministic fixed-size part names avoid generating a new pathname per cycle. Every part, full raw SHA256, exact count, length, order, cycle and root JSON object are checked. Corruption, wrong paths, missing parts and partial generations fail closed. Existing production gzip writer explicitly refuses to overwrite chunked input: the writer, transaction and authority are still absent.

An authenticated copy-only real original source test reconstructs the entire historical state into a temporary directory. No production workflow, main Observer/legacy UI, original growth state, journal, heartbeat identity or external repository is modified.

**Future gates:** default-off format-preserving chunk writer across every original writer, coherent multi-file Git commit and matching recovery ticket, strict source-identity and verified full-cycle tests, stable Git storage growth, old/new browser observer parity and one full post-cutover clean restart with two durable natural cycles. The no-activation boundary remains mandatory.
