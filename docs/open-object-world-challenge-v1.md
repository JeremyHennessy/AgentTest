# Open Object World Challenge v1

Status: isolated research only. No live environmental action authority.

Production base: `bd78db8342d267822795f59a395fe5958beeed84`.

## Purpose

Bring the richer 5×5 world back into the active research queue after the retention prerequisites were removed from the critical path.

This world is intentionally not a dataset and not a scripted task. It gives the explorer persistent local physics, multiple objects, a partition, two independently controlled gates and one optional far-side affordance. The explorer receives only local public observations and generic action receipts.

There is no authored goal, reward score, target path or solution script.

## Public action set

Unchanged generic actions:

- north / east / south / west
- inspect
- interact
- take
- drop
- push

The explorer is the same kind of deterministic least-tried public-action policy used in the earlier object-world research. It does not inspect private entity fields and does not contain gate-specific, object-specific or layout-specific rules.

## World structure

The 5×5 world is split by a solid partition with two gates.

Portable forms:
- one heavier movable form;
- two lighter movable forms on the starting side;
- one additional portable form on the far side.

Publicly visible mechanisms:
- a marked floor plate;
- a recessed slotted fixture;
- an unmarked pivot fixture on the far side.

Private mechanics are deliberately omitted from observations. They exist only so the environment has stable causal structure.

The pressure route admits more than one physical solution because multiple portable masses can combine. The slotted route admits more than one interaction pattern involving its compatible portable form. The far-side pivot is an optional loose affordance: it is not required to cross the partition and is not advertised as a goal.

Four layouts mirror the same hidden mechanics spatially while preserving public entity identities.

## Predeclared unguided hypothesis

Within 1,600 generic public actions per layout, without reward/goal/solution guidance or hidden-state access:

- all four layouts cross the partition;
- all four observe at least one gate open;
- at least three layouts observe both gates open;
- at least three layouts activate at least two distinct mechanisms;
- all four use inventory;
- all four preserve the exact public observation across a JSON state roundtrip halfway through.

The optional far-side pivot is reported but not required for acceptance.

A failure does not authorize simultaneous policy/world retuning. Inspect the trace, identify the first limiting mechanism, and test one change at a time.

## Progress definition

Progress is public and behavioral:

- new public observation states;
- inventory use;
- mechanism state changes;
- gate state changes;
- crossing from the starting side to the opposite side;
- persistence through world-state serialization.

No private mechanism flag, hidden objective, or reward is counted as discovery.

## Authority boundary

This research branch does not:

- change `src/agenttest/**`;
- modify live state;
- integrate with the production heartbeat;
- grant Action Lab or Planning Lab authority over this world;
- count anything toward Phase42 or Phase43;
- tune Phase42 scoring;
- change agenda limits;
- activate a model provider or OpenAI API;
- alter Observer/UI.

If the world itself passes, the next boundary is reviewed shadow observation + native observe/inquire on copied state. New environmental action authority remains a later, separate checkpoint.
