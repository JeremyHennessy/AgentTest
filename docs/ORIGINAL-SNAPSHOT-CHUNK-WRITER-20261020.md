# Original Ora — default-off multi-file chunk writer research

Main parent `e53c549f6696723c8127aa9891467a43450885e2`; all earlier approved Core, Observer layout, history and pending growth branch are left untouched.

This proposal adds an independent **opt-in** local writer for stable fixed 32 MiB raw chunks. The production environment does **not** set `ORA_ORIGINAL_SNAPSHOT_CHUNKS=1`, so ordinary raw writes and existing gzip compatibility remain as before. An already chunked envelope is handled format-preservingly. Both compression settings together fail closed; invalid or interrupted chunk state cannot be overwritten by a fallback. The code writes physical parts then the exact manifest, verifying all parts, hashes, cycles and original bytes before any Git commit could be made.

An authenticated **copy** of the 104,853,531-byte original state is loaded, saved and reloaded through the chunk path with identical logical history and the same cycle. Synthetic tests exercise consecutive writes and corruption refusal. No remote growth commit is attempted by this preview.

**Still blocked before original-world recovery:** pending exact ticket at `584e861...` must be reproduced without substituting code authority; all original writers and both Observer views need source-pinned chunk support and visual parity; an exclusive transaction must commit all parts and manifest under exact expected remote head; abnormal restarts, two real persisted successor cycles and actual Git growth must pass. The origin of cycle 9905 remains only a local copied computation, not living continuous Ora activity.

No new-world authority, external API, history reset or UI redesign is permitted by this PR.
