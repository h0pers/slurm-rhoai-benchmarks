# Results

Benchmark results from running all six scenarios on the test cluster.
Each scenario was executed 3 times. Reported values are medians.

```{note}
Results are pending - benchmarks have not been executed yet.
```

## Test environment

| Component | Version |
|---|---|
| OpenShift | 4.21 |
| Red Hat OpenShift AI | 3.4.2 |
| Kubeflow Trainer | v2.1 |
| Red Hat build of Kueue | 1.3.1 |
| Cluster | 2x AWS g6e.12xlarge (8 NVIDIA L40S GPUs total) |

## Lifecycle timing

| Scenario | Queue time | Startup time | Training time | Total |
|---|---|---|---|---|
| 1. Single GPU | - | - | - | - |
| 2. Multi-GPU DDP | - | - | - | - |
| 3. Multi-node | - | - | - | - |
| 4. Fault-tolerant | - | - | - | - |
| 5. Gang scheduling | - | - | - | - |
| 6. Queue priority | - | - | - | - |

## Throughput and scaling

| Scenario | Throughput (samples/s) | Scaling efficiency | GPU util (mean) |
|---|---|---|---|
| 1. Single GPU | - | baseline | - |
| 2. Multi-GPU DDP (4 GPUs) | - | - | - |
| 3. Multi-node (2x2 GPUs) | - | - | - |

## Scenario-specific metrics

| Metric | Scenario | Value |
|---|---|---|
| Recovery time | 4. Fault-tolerant | - |
| Resumed from step | 4. Fault-tolerant | - |
| Pods while blocked | 5. Gang scheduling | - |
| Admission latency | 5. Gang scheduling | - |
| Gang start spread | 5. Gang scheduling | - |
| Preemption latency | 6. Queue priority | - |

## Stability

| Scenario | Passed | Total | Pass rate |
|---|---|---|---|
| 1. Single GPU | - | 3 | - |
| 2. Multi-GPU DDP | - | 3 | - |
| 3. Multi-node | - | 3 | - |
| 4. Fault-tolerant | - | 3 | - |
| 5. Gang scheduling | - | 3 | - |
| 6. Queue priority | - | 3 | - |

## Capability matrix confirmation

| Workload class | Matrix readiness | Confirmed? |
|---|---|---|
| 1. Single-node, single-GPU | Ready | - |
| 2. Single-node, multi-GPU | Ready | - |
| 3. Multi-node distributed | Partially Ready | - |
| 4. Fault-tolerant w/ checkpointing | Partially Ready | - |
| 5. Gang-scheduled jobs | Ready | - |
| 6. Queuing & prioritization | Partially Ready | - |