# Semantic Memory and World Claims

Phase 4 separates three things that are often incorrectly collapsed into one AI memory system.

## 1. Episodic evidence

Episodes are the raw record of what was observed or supplied. They are not deleted when summaries are created.

## 2. Semantic memory

Semantic memory is a deterministic index over episode concepts.

For each concept it stores occurrence count, first and last cycle, and source episode IDs. Pairwise co-occurrence creates association edges with counts and source episode IDs.

Semantic memory is a retrieval aid. It does not become evidence merely because a concept appears frequently.

## 3. World claims

World claims are explicit subject-predicate-value records with provenance.

Observed repository fields produce confidence-1.0 sensor-derived claims. Prediction evaluations and explicit experiment outcomes also produce claims.

When a value changes, the old claim is retained with status superseded and linked to the new current claim. This makes temporal revision inspectable.

## Why this matters

A persistent system needs to remember not only its current model but how that model changed. Otherwise later summaries can overwrite inconvenient prior states and create the illusion that it always knew the current answer.

Phase 4 therefore treats contradiction, revision, and provenance as first-class history.
