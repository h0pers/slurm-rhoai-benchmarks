# Scenarios

Six scenarios cover workload classes 1-6. Each is defined in a YAML
file under `scenarios/` and executed by its matching notebook.

| # | Scenario | Class | Shape | What it proves |
|---|---|---|---|---|
| 1 | `single-gpu` | Single-node, single-GPU | 1 node, 1 GPU | baseline throughput, full lifecycle timing |
| 2 | `multi-gpu-ddp` | Single-node, multi-GPU | 1 node, 4 GPUs (DDP) | intra-node scaling efficiency |
| 3 | `multi-node` | Multi-node distributed | 2 nodes, 2 GPUs each (NCCL) | inter-node scaling, implicit gang start |
| 4 | `fault-tolerant` | Fault-tolerant w/ checkpointing | 2 nodes, 2 GPUs each + NFS checkpoint + worker kill | recovery and checkpoint resume |
| 5 | `gang-scheduling` | Gang-scheduled jobs | blocker 4 GPUs + measured 6 GPUs | all-or-nothing admission |
| 6 | `queue-priority` | Queuing and prioritization | low-priority 6 GPUs vs high-priority 4 GPUs | priority-based preemption and requeue |
| 7 | - | HPC math algorithms | not benchmarked | [excluded](#class-7-hpc-mathematical-algorithms-not-benchmarked) - platform gaps (RoCE, topology, heterogeneous nodes) |

## Training workload (scenarios 1-4)

- **Model:** DistilBERT fine-tuning on a fixed 4000-sample IMDB subset.
- **Length:** 200 steps (scenarios 1-3) or 600 steps (scenario 4 - long
  enough to survive the fault injection and resume from checkpoint).
- **Script:** identical across all four. Only topology and checkpointing
  vary, so differences come from the platform, not the workload.
- Deliberately small. We measure platform behavior, not model quality.

## Scheduling workload (scenarios 5-6)

- GPU-holding sleep jobs with no training and no package installs.
  Admission timing is not polluted by setup cost.
- Run on a dedicated ClusterQueue (`bench-cq`) with preemption enabled.

## Class 7: HPC mathematical algorithms (not benchmarked)

Class 7 covers tightly-coupled multi-node GPU computations - linear
algebra solvers, FFT, PDE stencils, molecular dynamics. These workloads
exchange data between GPUs many times per second and need low-latency
interconnects to perform well.

**Why it is not benchmarked.** The platform capabilities this class
depends on are not production-ready:

| Gap | Status in RHOAI 3.4 |
|---|---|
| RoCE / GPUDirect RDMA | Tech Preview, not GA |
| Switch-level network topology in Kueue | Not available |
| Heterogeneous jobs (mixed GPU + CPU-only nodes) | Not available |

Running these workloads over standard Ethernet would measure network
bottlenecks, not platform capability. The capability matrix already
documents this class as *Not Ready*.

**What a future benchmark would use.** Once RoCE reaches GA, candidate
workloads include:

| Benchmark | What it measures |
|---|---|
| [HPL](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks) (NVIDIA HPC-Benchmarks) | Dense linear algebra (Linpack) - the TOP500 standard |
| [HPCG](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks) (NVIDIA HPC-Benchmarks) | Sparse iterative solver - stresses memory and interconnect |
| [PyHPC-Benchmarks](https://github.com/dionhaefner/pyhpc-benchmarks) | Equation of State and Isoneutral Mixing via PyTorch/CuPy |

The benchmark would run HPL or HPCG across 2+ nodes with GPUDirect
enabled, measuring multi-node throughput and comparing against Slurm's
native MPI launch (`srun --mpi=pmi2`). Key metrics: GFLOPS, inter-node
bandwidth, and GPU-to-GPU latency.

Class 7 re-enters scope when RoCE reaches GA.

## Pass criteria

Each scenario carries explicit pass criteria in its YAML (`checks`
field). The CLI checks them after each run and records `passed` plus any
failures in `result.json`.