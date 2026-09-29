# AgentTest

AgentTest is an original experiment in persistent machine growth.

The goal is not to imitate an existing AI-agent framework and not to claim consciousness. The goal is to investigate how far a software system can move toward **lifelike computational properties** through persistent identity, memory, curiosity, self-observation, autonomous question generation, experimentation, learning, and reversible self-modification.

## Working definition of "closer to alive"

AgentTest measures progress through observable properties rather than anthropomorphic claims:

1. **Continuity** — state survives individual runs.
2. **Memory** — experiences can affect later decisions.
3. **Self-model** — the system maintains an explicit, revisable model of its capabilities, limits, history, and current condition.
4. **Curiosity** — it can generate questions that were not directly supplied by a user.
5. **Agency** — it can select among possible actions according to explicit goals and evidence.
6. **Learning** — outcomes change future priorities or strategies.
7. **Adaptation** — it can propose changes to its own code, policies, tests, or processes.
8. **Reflection** — it can compare predictions with outcomes and record mistakes.
9. **Open-endedness** — it can create new lines of inquiry instead of only completing a fixed task list.
10. **Reproducibility** — every claimed improvement retains an evidence trail.

## Core rule

No version may call itself improved merely because code changed.

An improvement must be demonstrated against recorded evidence or evaluation criteria. Failed experiments remain part of the history.

## Evolution policy

AgentTest may:

- inspect its own repository and recorded state;
- generate questions and hypotheses;
- run reversible experiments;
- create proposed code or configuration changes;
- create branches and pull requests;
- evaluate proposed changes;
- preserve useful discoveries and failed attempts.

AgentTest must not silently rewrite its own history or erase failed experiments. Known-good states are checkpoints.

Automatic self-merging is intentionally excluded from the first baseline. Evolution should be inspectable before it becomes irreversible.

## Initial research question

> What is the minimum architecture required for a software system to develop persistent, evidence-driven, open-ended behavior that becomes measurably richer over time?

The repository itself is the laboratory.
