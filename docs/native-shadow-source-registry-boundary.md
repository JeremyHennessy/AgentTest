# Native shadow source registry boundary

Status: isolated source-identity proof only. No live activation is authorized.

Production baseline: `main@eb906904d4a30d7427075987f928e0b97699cfe3`.

## Why this exists

PR #177 showed that an unsigned fixed public-stream fixture can stage a native temporal inquiry into a copied production Core and coexist with the bounded agenda. That does not answer whether a future observation stream corresponds to reviewed producer code.

This gate defines one narrow trust level: **Git-object-pinned shadow source**.

It does not call that source signed or production-authenticated.

## Reviewed source

The only registry entry is `research.open-object-world-v0`, bound to:

- repository `JeremyHennessy/AgentTest`;
- commit `dcb03f13ad37bcc84543bfa9f42c5be04095feb3`;
- `experiments/open_object_world.py` blob `f25a43b148a8009fa85a375184a484e6d54434b8`;
- `experiments/open_object_world_explorer.py` blob `afafba3ff6ea59de239b071d81c36a37b5cfe0e8`;
- observation schema `open-object-world-v0`.

The explorer is included because the shadow workflow needs a deterministic public-stream driver. Its inclusion **does not grant Ora action authority**.

## Trust semantics

A workflow attestation is valid only if the exact Git commit and every reviewed component blob match the registry entry. The resulting manifest remains:

- `activation_scope=shadow_only`;
- `signed_source=false`;
- `allow_live_activation=false`;
- environment action authority=false;
- Action Lab authority=false;
- Planning Lab authority=false;
- Phase42 credit=false.

GitHub/Git object verification establishes that the shadow workflow executed reviewed bytes. It does not cryptographically prove the origin of an arbitrary later runtime message. A future live source needs a stronger runtime identity/authentication design.

## Public-output check

The dedicated workflow extracts the exact pinned source components into runner temporary storage, generates 240 public transitions in each of the four layouts using the pinned explorer, and fails if an observation/entity or action receipt exposes a private key.

No hidden world state is uploaded as evidence.

## Retention is deliberately not implemented here

The current organism evidence ledger is append-oriented. Episode IDs are allocated from episode-list length. Deleting historical evidence entries would therefore risk later ID reuse/collision unless allocation semantics change.

A separate `fix/state-storage-blob-guard` branch currently specifies compact snapshots and journal rollover through tests but does not implement them; its verify run is failing by design against current StateStore behavior.

This registry work does not modify that branch and does not add pruning/tombstoning behavior. Production cumulative-evidence retention remains a separate prerequisite before live activation.
