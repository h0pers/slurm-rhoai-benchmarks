# Methodology

What we benchmark, how, and why. For step-by-step instructions see the
[Runbook](runbook.md).

## Glossary

| Term | Meaning |
|---|---|
| **TrainJob** | A Kubernetes object that describes a training run - how many nodes, GPUs, and what script to run. Similar to an `sbatch` script in Slurm. |
| **Workload** | A Kueue object created automatically for every TrainJob. Tracks the job's resource request and queue position. |
| **Admission** | The moment Kueue grants a Workload its requested resources. Nothing runs until admission happens. |
| **Gang scheduling** | All-or-nothing scheduling. A job needing 4 GPUs across 2 nodes either gets all 4 or waits - no partial starts. |
| **Preemption** | A higher-priority job forces a lower-priority one to stop and release its resources. The evicted job re-enters the queue. |
| **ClusterQueue** | A cluster-wide resource pool with GPU/CPU/memory quotas. Administrators create these. |
| **LocalQueue** | A namespace-scoped entry point into a ClusterQueue. Users submit jobs here. |
| **JIT checkpoint** | Just-in-time checkpointing. On shutdown signal, the training script auto-saves its state to shared storage. On restart, it resumes from the saved point. Zero code changes needed. |
| **NCCL** | NVIDIA Collective Communications Library - the standard for GPU-to-GPU communication during distributed training. |
| **DDP** | Distributed Data Parallel. Each GPU trains on a different data slice. Gradients are synchronized after each step. |

## Objective

Produce reproducible measurements of how OpenShift AI handles
representative Slurm workload classes. Results confirm or correct the
classifications in the Slurm vs RHOAI Capability Matrix.

Benchmarks run on OpenShift AI only. Slurm 26.05 behavior comes from
official documentation, not hardware measurements.

## Baseline versions

| Component | Version | Role |
|---|---|---|
| OpenShift | 4.21 | cluster platform |
| Red Hat OpenShift AI | 3.4.2 | GA release under test |
| Kubeflow Trainer | v2.1 (API v1alpha1) | training job orchestration |
| Red Hat build of Kueue | 1.3.1 | queueing and scheduling |
| Slurm | 26.05 | documented comparison baseline |

**Test cluster:** 2 AWS `g6e.12xlarge` nodes (4 NVIDIA L40S GPUs each,
8 GPUs total), gp3 EBS + NFS (RWX) storage, DCGM GPU metrics enabled.

## Procedure

1. One-time cluster setup: `oc apply -f manifests/`.
2. Each scenario runs **3 repetitions**. Counted runs use *Restart
   Kernel & Run All* to avoid hidden state.
3. Scenarios 5-6 run alone - their queue shares physical GPUs with the
   `default` queue.
4. Reported values: median across repetitions. Stability = pass rate.
5. A run is valid even if GPU utilization query fails (the error is
   recorded). It is invalid if any pass criterion fails.

## Reporting

Each scenario verdict either confirms the documented readiness level or
triggers a matrix correction with run artifacts as evidence. See
[Results](results.md) for the full breakdown.