# Design: Genesis Phases 0–2

## Premise

AgentTest is not an imported agent framework. It is an experiment in building measurable organism-like computational properties from simple, inspectable mechanisms.

There is deliberately no scalar "alive score."

## Current closed loop

```
repository perception
       ↓
compare with prior prediction ─────→ prediction error
       ↓                              ↓
persistent memory                  internal drives
       ↓                              ↓
environmental surprise ─────────→ chosen intention
                                      ↓
                              generated question
                                      ↓
                           falsifiable experiment
                                      ↓
                           next-state prediction
                                      ↓
                              next heartbeat
```

This is the first phase where the system can create and close an evidence loop without a human supplying the outcome: a repository-state prediction is evaluated by the next repository observation.

## Drives are not emotions

The drive values are numerical control pressures derived from recorded state. Names such as `evidence_hunger` and `novelty_hunger` are engineering shorthand, not claims of subjective feeling.

The current drives are:

- `prediction_error`: a measured expectation was violated;
- `evidence_hunger`: unresolved experiments are accumulating;
- `uncertainty`: open questions are accumulating;
- `continuity_repair`: persistent continuity is not yet established;
- `calibration_gap`: the self-model lacks predictive evidence;
- `novelty_hunger`: inquiry is becoming repetitive.

## Anti-busywork rule

When evidence hunger is dominant, the loop selects an existing unresolved experiment instead of creating another one. This prevents activity volume from masquerading as advancement.

## Prediction discipline

Predictions cover only fields that the repository sensor actually measures. A violated prediction records the exact error fields. It does not infer a cause.

## Still missing

- model-backed generative cognition;
- broad environmental perception;
- independent environmental action;
- semantic long-term memory;
- a richer causal/world model;
- self-authored code proposals;
- any evidence of subjective experience.
