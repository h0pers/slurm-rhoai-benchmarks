# Results

Benchmark results for RHOAI (Trainer v2.1 + Kueue 1.3.1) across six
workload scenarios. Each scenario ran 3 times. Values are medians.

Run dates: 2026-07-13 and 2026-07-14.

## Test environment

| Component | Version |
|---|---|
| OpenShift | 4.21 |
| Red Hat OpenShift AI | 3.4.2 |
| Kubeflow Trainer | v2.1 |
| Red Hat build of Kueue | 1.3.1 |
| Cluster | 2x AWS g6e.12xlarge (4 NVIDIA L40S GPUs per node, 8 total) |

## Test workload

All training scenarios use the same model and dataset to keep
comparisons fair. This is a small workload designed to test that each
capability works correctly, not to stress-test performance.

| Parameter | Value |
|---|---|
| Model | DistilBERT (~66M parameters) |
| Dataset | IMDB sentiment, 4000 samples |
| Batch size | 16 per GPU |
| Training steps | 200 (scenarios 1-3), 600 (scenario 4) |

## Summary

All 6 scenarios passed every run (18/18). Single-GPU and multi-GPU
training work out of the box. Multi-node training works after a
one-time runtime patch (increasing shared memory from the default
64 MB - see the [runbook](runbook.md)). Checkpointed training
recovers from a pod failure in 4 seconds. Gang scheduling correctly
holds jobs when resources are unavailable. Priority preemption evicts
lower-priority work in under 1 second and automatically requeues it
afterward.

## Lifecycle timing

All times in seconds.

- **Queue** - how long a job waited for GPU resources
- **Startup** - pod creation through first training step
- **Training** - actual model training
- **Total** - end-to-end wall clock

| Scenario | Queue | Startup | Training | Total |
|---|---|---|---|---|
| 1. Single GPU | 0.0 | 1.0 | 36.0 | 38.0 |
| 2. Multi-GPU DDP (4 GPUs, 1 node) | 0.0 | 1.0 | 50.0 | 51.0 |
| 3. Multi-node (4 GPUs, 2 nodes) | 0.0 | 1.0 | 75.0 | 76.0 |
| 4. Fault-tolerant (4 GPUs, 2 nodes) | 0.0 | 71.0 | 209.0 | 281.0 |
| 5. Gang scheduling | 182.0 | 2.0 | 35.0 | 219.0 |
| 6. Queue priority | 0.0 | 2.0 | 36.0 | 38.0 |

**What these numbers mean:**

- Jobs start in about 1 second when GPUs are free. No scheduling delay.
- Scenario 4 startup (71s) includes: initial training for 60 seconds,
  a deliberate worker pod kill, and 4 seconds of recovery. The extra
  time is the fault-tolerance test, not slow startup. See
  [Fault tolerance](#fault-tolerance-scenario-4) for the breakdown.
- Scenario 5 queue time (182s) is intentional. A blocking job holds
  GPUs for 180 seconds to verify that the system waits correctly
  rather than partially starting the job.

## Throughput and scaling

Scaling efficiency measures how much of the ideal speedup you actually
get when adding GPUs. If 4 GPUs were 4x faster than 1 GPU, efficiency
would be 100%.

| Scenario | Throughput | Speedup | Efficiency | GPU util |
|---|---|---|---|---|
| 1. Single GPU | 506 samples/s | baseline | - | see note |
| 2. Multi-GPU DDP (4 GPUs, 1 node) | 660 samples/s | 1.3x | 33% | 94% |
| 3. Multi-node (4 GPUs, 2 nodes) | 281 samples/s | 0.56x | 14% | 68% |
| 4. Fault-tolerant (4 GPUs, 2 nodes) | 215 samples/s | - | - | 96% |

**Why efficiency is low:**

The test model is very small (66M parameters, 4000 samples). GPUs
finish computing faster than they can synchronize with each other.
This is like hiring 4 people to write a 1-page memo - the overhead of
coordinating outweighs the work itself.

- **Multi-GPU DDP (33%):** 4 GPUs on one node are 1.3x faster than
  1 GPU. The overhead comes from GPUs exchanging model updates after
  each training step. With a larger model (billions of parameters),
  each GPU has more work to do between exchanges, and efficiency
  improves significantly.
- **Multi-node (14%):** 4 GPUs across two nodes are slower than
  1 GPU. Adding network hops between machines makes the coordination
  overhead even larger. This result confirms multi-node training
  *works*, but says nothing about how it would perform on a real
  production workload.
- **Fault-tolerant:** Not directly comparable because this scenario
  uses 3x more training steps (600 vs 200), saves checkpoints to
  disk, and includes a mid-training disruption.

**GPU utilization note:** GPU utilization is sampled from Prometheus
during each run. Some monitoring queries timed out for scenarios 1
and 2, so utilization data is incomplete. Where measurements succeeded:
single-GPU showed 18% (expected for a model that doesn't fully use a
modern GPU), multi-GPU showed 93-96%, multi-node showed 68%, and
fault-tolerant showed 96%. Training results are valid regardless of
monitoring gaps.

## Scenario-specific metrics

### Fault tolerance (Scenario 4)

A worker pod is deliberately killed 60 seconds into training to test
recovery. Training saves checkpoints (snapshots of progress) to a
shared disk every 50 steps, so it can resume from the last save point.

| Metric | Value | What it means |
|---|---|---|
| Recovery time | 4s | After a worker pod is killed, all pods are recreated and training resumes in 4 seconds. |
| Resumed from step | 100 | Training picks up from the last checkpoint, not from the beginning. At most 50 steps of work (the checkpoint interval) can be lost. |
| Checkpoint save interval | every 50 steps | How often progress is saved to disk. Smaller intervals mean less lost work but slightly slower training. |

### Gang scheduling (Scenario 5)

A job needing 6 GPUs is submitted while a blocking job holds 4 of 8
available GPUs. Gang scheduling (all-or-nothing admission) means the
system should not start any part of the job until all resources are
available.

| Metric | Value | What it means |
|---|---|---|
| Pods created while blocked | 0 | The system created no worker pods while resources were unavailable. No GPUs were wasted on partial starts. |
| Admission latency | 1s | After the blocking job finished and freed its GPUs, the waiting job was admitted in 1 second. |
| Gang start spread | 0s | All worker pods started at the same time. None waited for the others. |

### Queue priority (Scenario 6)

A low-priority job is running on the cluster when a high-priority job
is submitted. Preemption (stopping lower-priority work to make room
for higher-priority work) should kick in automatically.

| Metric | Value | What it means |
|---|---|---|
| Preemption latency | <1s | The low-priority job was stopped and the high-priority job started in under 1 second. |
| Low-priority requeued | Yes | After the high-priority job finished, the low-priority job was automatically restarted. No manual intervention needed. |

## Stability

| Scenario | Passed | Total | Pass rate |
|---|---|---|---|
| 1. Single GPU | 3 | 3 | 100% |
| 2. Multi-GPU DDP | 3 | 3 | 100% |
| 3. Multi-node | 3 | 3 | 100% |
| 4. Fault-tolerant | 3 | 3 | 100% |
| 5. Gang scheduling | 3 | 3 | 100% |
| 6. Queue priority | 3 | 3 | 100% |

All 18 runs passed after applying the one-time runtime patches
described in the [runbook](runbook.md). Without these patches:

- **Multi-node scenarios (3, 4)** crash on startup. The default 64 MB
  `/dev/shm` is too small for PyTorch cross-node communication.
- **Fault-tolerant scenario (4)** fails to save checkpoints. The SDK's
  per-job volume mount is silently dropped on this cluster, so the
  shared disk never appears inside the pod.
- **Fault-tolerant scenario (4)** cannot recover from a pod failure.
  Default Kubernetes restart behavior (CrashLoopBackOff) restarts pods
  independently with increasing delays, so distributed workers never
  reconnect. Requires `backoffLimit: 0` with `failurePolicy.maxRestarts`
  to force synchronized restarts.

Once patched, behavior was consistent across all runs.

## Capability matrix confirmation

Maps benchmark results to the workload readiness classifications from
the capability matrix.

| Workload class | Matrix rating | Benchmark result | Correction needed? |
|---|---|---|---|
| 1. Single-node, single-GPU | Ready | 3/3 pass. Instant admission, 1s startup. Works out of the box. | No |
| 2. Single-node, multi-GPU | Ready | 3/3 pass. DDP works correctly, all 4 GPUs participated. | No |
| 3. Multi-node distributed | Partially Ready | 3/3 pass after one-time runtime patch (increase /dev/shm from 64 MB). Tested on standard pod network only - RoCE (RDMA over Ethernet, for high-speed inter-node networking) is Tech Preview and was not tested. | No |
| 4. Fault-tolerant w/ checkpointing | Partially Ready | 3/3 pass. 4s recovery, correct checkpoint resume. JIT checkpointing (Early Access) works well. Elastic training (resizing a running job) remains a gap and was not tested. | No |
| 5. Gang-scheduled jobs | Ready | 3/3 pass. 0 leaked pods, 1s admission, simultaneous pod start. Textbook all-or-nothing behavior. | No |
| 6. Queuing & prioritization | Partially Ready | 3/3 pass. Sub-second preemption, automatic requeue. Backfill scheduling (filling idle gaps with smaller jobs) is a workaround and was not tested. Job arrays (batch parameter sweeps) are a gap. | No |
| 7. HPC math algorithms | Not ready | Not benchmarked. Requires RDMA networking and heterogeneous job support, neither available on this cluster. | - |

No corrections to the capability matrix are needed. All benchmark
results align with the documented readiness ratings.