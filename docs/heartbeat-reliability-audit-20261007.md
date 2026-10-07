# Heartbeat reliability evidence, 7 October 2026

The repair addresses three observed failure modes together: computation that failed to publish, a stopped successor chain, and success attributed to the wrong growth run. It does not change Ora's cognitive policy or establish a learning improvement.

## Fixed population and sample

The audit covers workflow creation times from **2026-10-06 17:33:00 UTC through 2026-10-07 17:33:00 UTC**. All 2,080 unique repository runs were retrieved in four adjacent six-hour slices and 23 pages, with fetched counts matching slice totals. Filtering the growth, controller and reconciliation workflow IDs yielded 1,925 runs across 19 source SHAs.

| Workflow | Success | Failure | Cancelled | Skipped | Queued | Total |
|---|---:|---:|---:|---:|---:|---:|
| Growth | 897 | 6 | 2 | 0 | 0 | 905 |
| Controller | 897 | 12 | 0 | 0 | 0 | 909 |
| Reconciliation | 16 | 0 | 24 | 70 | 1 | 111 |

All 18 failed job logs were inspected. Successful sampling was deterministic within each workflow/source-SHA stratum: first/lower-median/last for strata with at least 20 successes, otherwise the lower-median. This selected 62 logs covering every successful source era. Two additional publication/recovery controls and all eight unusually short successful controllers produced 90 complete inspected logs in total. The 26 cancellations and queued ghost had zero jobs and no runner logs. The later rerun of controller 37655393894 was excluded by restoring its original failed attempt in this fixed-window aggregate.

## Failures and recovery

[Growth 37642225155](https://github.com/JeremyHennessy/AgentTest/actions/runs/37642225155) completed computation and checks, created local commit 81e6ab1e, then received a remote Git Internal Server Error at 15:12:24. [Its controller](https://github.com/JeremyHennessy/AgentTest/actions/runs/37641730812) exhausted five successor dispatch HTTP 500 attempts. [Growth 37655413138](https://github.com/JeremyHennessy/AgentTest/actions/runs/37655413138) likewise completed its work and made local 984b1099, but failed publication at 16:53:17; [controller attempt 1](https://github.com/JeremyHennessy/AgentTest/actions/runs/37655393894/attempts/1) exhausted five successor HTTP 500s. Both ordinary runs had the bounded-investigation gate off. Neither exposed a recovery artifact. Their unuploaded output is not claimed durable.

The other four growth failures were correct exact-source-CI refusals before Core after source 3529f5c7. Other controller failures included one earlier dispatch HTTP 500 and three reconciliation-lane wait timeouts; successors restored progress in those cases. Neither chain-stopping incident was a cognition or invariant failure.

Successful publications around the first interruption were c05ada67 at 15:02:18 and 72123f0c at 16:37:14, 94m56s apart. The last successful in-window publication was f03b1d6d at 16:51:57.550. The next local 984b1099 did not publish. Independent of the fixed audit, the controlled 17:33 restart later published cycles 6536/6537 as 2f0a279f and cec16fd2 on source 87fec405. Restoration is separate from the permanent reliability repair.

Large-file warnings also occurred on successful pushes, including larger organism files than either failed push. They establish storage pressure, not the cause of GitHub's 500 responses.

## Incorrect run correlation

Eight green controllers watched an older successful growth run instead of the child they dispatched, then queued a successor early. All eight actual children eventually succeeded. This demonstrates false success attribution; state corruption or duplicate world actions were not established.

| Controller log | Dispatched child | Unrelated watched run |
|---|---:|---:|
| [37511755974](https://github.com/JeremyHennessy/AgentTest/actions/runs/37511755974) | 37511779283 | 37511616726 |
| [37556892955](https://github.com/JeremyHennessy/AgentTest/actions/runs/37556892955) | 37556907305 | 37556819697 |
| [37579145737](https://github.com/JeremyHennessy/AgentTest/actions/runs/37579145737) | 37579159432 | 37579048256 |
| [37587570594](https://github.com/JeremyHennessy/AgentTest/actions/runs/37587570594) | 37587584967 | 37587485058 |
| [37602547948](https://github.com/JeremyHennessy/AgentTest/actions/runs/37602547948) | 37602571603 | 37602359011 |
| [37628195832](https://github.com/JeremyHennessy/AgentTest/actions/runs/37628195832) | 37628214880 | 37511616726 |
| [37632746009](https://github.com/JeremyHennessy/AgentTest/actions/runs/37632746009) | 37632767970 | 37631889774 |
| [37637282032](https://github.com/JeremyHennessy/AgentTest/actions/runs/37637282032) | 37637300425 | 37613835503 |

Thirty of 38 inspected controller logs containing both dispatch and watch had matching IDs; eight did not. This targeted sample is not a prevalence estimate for all 909 controllers. At least eight defects in the complete population are directly verified.

## Consequences for the implementation

The [save/recovery contract](heartbeat-reliability.md) uses a compact remotely persisted request, the exact computed Git commit as publication identity, completed receipts in Git history, exact ticket-to-run matching, and independent recovery checks. A remote acknowledgment is verified by reading branch identity. An ambiguous dispatch can redeliver the same ticket without creating a new logical request.

A runner lost before saving its result can leave only a pending intent. Identical pure work may be recomputed; the original unsaved bytes cannot be reconstructed by claiming they were preserved. The guarantee is one accepted durable result per request, not exactly-once external effects or uninterrupted GitHub availability.

The raw Actions runs remain the source records. This repository report publishes the aggregate, sampling rule and directly linked failure/correlation evidence, without uploading raw state archives or complete logs.
