# Metrics

Every benchmark job goes through: **submit - admit - start - train -
complete**. The metrics below capture how long each phase takes, how
well GPUs are used, and whether scheduling features work correctly.

## Lifecycle timing

| Metric | What it measures | How it is captured | Why it matters |
|---|---|---|---|
| Queue time | Wait before admission | Submission to Workload `Admitted` condition | Slow admission = idle GPUs. Comparable to Slurm dispatch time. |
| Startup time | Admission to pods running | `Admitted` to container `startedAt` | Kubernetes overhead (image pull, pip install). Slurm on bare metal skips this. |
| Training time | Actual GPU compute | Pods running to TrainJob `Complete` | Should match Slurm for the same workload. |
| Time-to-complete | Total wall time | Sum of queue + startup + training | The number users care about: submit to done. |

## Throughput and efficiency

| Metric | What it measures | How it is captured | Why it matters |
|---|---|---|---|
| Throughput | Samples processed per second | `[BENCH]` markers in Trainer logs | Scenario 1 sets the baseline for scaling comparison. |
| Scaling efficiency | How well throughput scales with more GPUs | throughput / (single-GPU throughput x GPU count) | 1.0 = perfect scaling. Real values are lower due to gradient sync overhead. |
| GPU utilization | Percentage of GPU compute cycles used | Average `DCGM_FI_DEV_GPU_UTIL` from Prometheus/Thanos | Confirms GPUs did real work and not sitting idle. |

## Stability

| Metric | What it measures | How it is captured | Why it matters |
|---|---|---|---|
| Pass rate | Reliability across repeated runs | Passed runs / total (3 per scenario) | One success could be luck. Repeating catches flaky behavior. |

## Scenario-specific

| Metric | Scenario | What it measures | Why it matters |
|---|---|---|---|
| Recovery time | 4 (fault-tolerant) | Time from pod kill to all pods running again | Comparable to Slurm checkpoint-restart recovery. |
| Admission latency | 5 (gang scheduling) | Blocker done to measured job admitted | Long delay = idle GPUs between jobs. |
| Gang start spread | 5 (gang scheduling) | Max - min pod `startedAt` | Should be near zero. Large spread defeats gang scheduling purpose. |
| Preemption latency | 6 (queue priority) | High-priority submit to low-priority evicted | How fast the scheduler reacts to priority conflicts. |

## How timestamps work

All timestamps come from the Kubernetes API (condition
`lastTransitionTime`, container `startedAt`) - never from the harness
clock. The 5-second poll interval does not affect precision: even if we
notice a condition late, the recorded time is when it actually happened
on the server.