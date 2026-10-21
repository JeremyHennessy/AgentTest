# Original Ora — default-off compressed writer preview

**Status:** test-only writer mechanism; no original-world recovery authorized by this PR. Exact source parent: `566e65f7e95cb636263f020a3359dc987fc8ce06`.

This patch implements lossless stable-path compressed writes while **preserving existing raw JSON behavior when the opt-in environment variable is absent**. Format detection refuses corrupted existing compressed state rather than overwriting it or falling back to an older snapshot. A single exclusive writer must commit `state/organism.json` and `state/snapshot-current.json.gz` **together** under the exact original growth Git parent; this helper never publishes a Git commit.

Affected runtime serialization paths: StateStore; current-world claim write; experiment-design and blocked-attention diagnostics. Read-only scripts were covered by merged #270. The branch's authentic original-copy workflow must verify preservation, cold reload, exact source blob and unchanged original branch. Unit tests cover raw default, initial opt-in, subsequent stable reuse, corruption refusal and invalid configuration.

**Not complete:** human-interaction workflow inline JSON reads, legacy + current Observer, Phase 42 shadow workflow's original-source fetch, pending 9904 claim recovery, whole-life authentic copied heartbeat with frozen input/source, concurrent writer transaction, two persisted successor cycles and sustainable Git repository size growth. The current draft is not a complete cutover and must not be used to enable `ORA_ORIGINAL_SNAPSHOT_GZIP` in production. No new world, API keys or other repository modifications.
