# Next Steps

The benchmarks in this project cover workload classes 1-6 using the
PyTorch runtime with Kueue. All six passed.
[Class 7](scenarios.md#class-7-hpc-mathematical-algorithms-not-benchmarked)
(HPC math algorithms) is not ready yet - it needs RDMA networking and
job types that RHOAI does not support today.

There are several ways to close this gap. Some add HPC capabilities
to Kubeflow Trainer (MPI runtime, Flux Framework). Others bring Slurm
itself into Kubernetes (Slinky operator). This page covers all three
approaches and asks: do we need to change Kubeflow Trainer at all if
a proven HPC scheduler can run alongside it?

## MPI runtime

MPI (Message Passing Interface) is the standard way HPC applications
talk between nodes. Think of it as the language that programs like
Linpack, HPCG, and molecular dynamics simulators use to split work
across many GPUs.

Kubeflow Trainer v2.0 added an MPI runtime. It lets you run MPI-based
workloads as regular TrainJobs - no manual setup needed.

**What the MPI runtime handles for you:**

- Creates SSH keys so nodes can talk to each other securely
- Builds the MPI hostfile (the list of machines in your cluster)
- Launches your program with `mpirun`

| | Detail |
|---|---|
| MPI libraries supported | OpenMPI, IntelMPI, MPICH |
| Works with | DeepSpeed, MLX, custom MPI apps |
| Available since | Trainer v2.0 (July 2025) |
| Available in RHOAI? | No. RHOAI 3.4 ships Trainer v2.1 but only bundles PyTorch runtimes |

**Why this matters.** Without an MPI runtime, HPC workloads like HPL
and HPCG cannot run on Trainer at all. The PyTorch runtime only
supports NCCL (GPU-to-GPU communication within PyTorch). MPI is what
traditional HPC applications need.

Sources:
[Trainer v2.0 release](https://github.com/kubeflow/trainer/releases/tag/v2.0.0),
[ML Policy docs](https://www.kubeflow.org/docs/components/trainer/operator-guides/ml-policy/)

## Flux Framework

[Flux](https://flux-framework.org/) is an HPC workload manager built
at Lawrence Livermore National Laboratory. It does everything the MPI
runtime does, plus it brings its own scheduler and resource manager
into Kubernetes.

Kubeflow Trainer v2.2 (March 2026) added Flux support. When you
create a TrainJob with a Flux runtime, an init container installs
Flux automatically - you do not need to change your application
container.

**What Flux adds beyond basic MPI:**

- **No SSH needed.** Flux connects nodes using a ZeroMQ overlay
  network instead of SSH. This removes the need for SSH keys, shared
  user IDs, and special permissions.
- **Topology-aware placement.** Flux knows the physical layout of
  your GPUs and CPUs and places jobs to reduce network hops.
- **Built-in scheduler.** Flux uses a graph-based scheduler that
  handles complex job dependencies and policies. It does not rely
  on the Kubernetes scheduler for every pod, which means higher
  throughput.
- **Interactive clusters.** You can shell into a running Flux cluster
  and submit jobs manually with `flux run`. This is useful for
  debugging HPC workloads before automating them.

| | Detail |
|---|---|
| MPI bootstrapping | ZeroMQ overlay (no SSH) |
| Topology awareness | fine-grained GPU and CPU placement |
| Available since | Trainer v2.2 (March 2026) |
| Available in RHOAI? | No. RHOAI 3.4 ships Trainer v2.1 |

Sources:
[Kubeflow Flux guide](https://www.kubeflow.org/docs/components/trainer/user-guides/flux/),
[Trainer v2.2 blog](https://blog.kubeflow.org/kubeflow-trainer-v2.2-release/),
[Flux Operator paper](https://f1000research.com/articles/13-203),
[KEP-2841](https://github.com/kubeflow/trainer/tree/master/proposals/2841-flux-hpc)

## Slinky - Slurm on Kubernetes

[Slinky](https://slinky.schedmd.com/docs/) lets you run Slurm inside
Kubernetes. Teams that already use Slurm keep their scripts and tools
(`sbatch`, `squeue`, `scontrol`) and get Kubernetes benefits like
container management and autoscaling on top.

Slinky was created by [SchedMD](https://www.schedmd.com/), the company
behind Slurm. NVIDIA uses it in production on 8,000+ GPUs. It reached
v1.0 in November 2025. A community
[guide for running it on OpenShift](https://github.com/redhat-hpc/slinky-on-openshift)
exists, but there is no Red Hat midstream build or official support.

Slinky has two modes. The **Slurm Operator** runs a complete Slurm
cluster on Kubernetes. The **Slurm Bridge** lets Slurm schedule
regular Kubernetes workloads, so existing pods benefit from Slurm's
scheduler without changing anything.

**What Slinky already covers.** The capability matrix
[gaps](results.md#capability-matrix-confirmation) - job arrays,
backfill scheduling, reservations, heterogeneous jobs - are standard
Slurm features. Slinky brings all of them to Kubernetes today.

Sources:
[Red Hat Developer article](https://developers.redhat.com/articles/2026/03/10/how-run-slurm-workloads-openshift-slinky-operator),
[NVIDIA Slinky](https://www.nvidia.com/en-us/software/slinky/),
[SchedMD announcement](https://www.schedmd.com/introducing-slinky-slurm-kubernetes/),
[GitHub](https://github.com/SlinkyProject/slurm-operator)

## Comparison

| | MPI runtime | Flux Framework | Slinky |
|---|---|---|---|
| What it does | adds MPI to Trainer | adds HPC scheduler to Trainer | runs Slurm on Kubernetes |
| MPI support | OpenMPI, IntelMPI, MPICH | all variants via ZeroMQ | native Slurm launcher |
| Topology awareness | relies on Kueue | built-in | built-in |
| Job arrays | no | no | yes |
| Heterogeneous jobs | no | no | yes |
| User interface | TrainJob YAML or SDK | TrainJob YAML | `sbatch` scripts |
| Maturity | Trainer v2.0 (July 2025) | Trainer v2.2 (March 2026) | 8,000+ GPUs in production |
| In RHOAI? | not bundled | not available | community guide only, no midstream |

MPI and Flux help nodes communicate better. They close the
communication gap. But the scheduling gaps - job arrays, backfill,
reservations - are problems Slurm solved years ago.

This raises a scope question. Is it reasonable for Kubeflow Trainer to
rebuild what a purpose-built scheduler already provides? Both tools
can run on the same cluster. Trainer handles ML training. Slurm
handles HPC scheduling. Each does what it was designed for.

## What this enables for Class 7

With an MPI or Flux runtime, the HPC benchmarks listed in the
[Class 7 section](scenarios.md#class-7-hpc-mathematical-algorithms-not-benchmarked)
become runnable on Kubeflow Trainer:

| Benchmark | What it measures | Notes |
|---|---|---|
| [HPL](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks) (Linpack) | dense linear algebra - the TOP500 standard | needs MPI or Flux |
| [HPCG](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/hpc-benchmarks) | sparse iterative solver - stresses memory and interconnect | needs MPI or Flux |
| [LAMMPS](https://www.lammps.org/) | molecular dynamics | Trainer v2.2 ships a ready-to-use Flux example |
| [PyHPC-Benchmarks](https://github.com/dionhaefner/pyhpc-benchmarks) | equation of state, isoneutral mixing | PyTorch/CuPy based |

**One dependency remains:** RoCE (RDMA over Converged Ethernet) must
reach GA for production-grade inter-node speed. Running these
benchmarks over standard Ethernet would measure network bottlenecks,
not HPC capability. See [results](results.md#capability-matrix-confirmation)
for the current Class 7 assessment.

## Recommendations

1. **Add an MPI ClusterTrainingRuntime to RHOAI.** The MPI plugin
   already exists in upstream Trainer v2.0, which RHOAI 3.4 ships as
   v2.1. Adding a bundled MPI runtime does not need a Trainer version
   upgrade - just a new runtime definition.

2. **Add Flux runtime when RHOAI upgrades to Trainer v2.2.** Flux
   provides stronger HPC capabilities (topology, scheduling,
   interactive clusters) but needs Trainer v2.2. When RHOAI adopts
   v2.2, Flux becomes available for inclusion.

3. **Re-run Class 7 benchmarks after RoCE reaches GA.** With an MPI
   or Flux runtime and production-grade RDMA networking, HPL and HPCG
   can produce meaningful results. Compare multi-node throughput and
   GPU-to-GPU latency against Slurm's native `srun --mpi=pmi2`.

4. **Track Workload-Aware Scheduling.** After Kubernetes v1.36,
   Kubeflow Trainer plans to add native gang scheduling without
   needing Kueue. This could simplify the scheduling stack for HPC
   workloads.

## Upstream issues to watch

| Issue | What it tracks |
|---|---|
| [trainer#2841](https://github.com/kubeflow/trainer/issues/2841) | Flux Framework KEP - design doc for the integration |
| [trainer#2249](https://github.com/kubeflow/trainer/issues/2249) | Slurm Runtime for Trainer v2 - run Slurm scripts on K8s |
| [trainer#1807](https://github.com/kubeflow/trainer/issues/1807) | IntelMPI support |
| [trainer#2903](https://github.com/kubeflow/trainer/issues/2903) | Elastic TrainJobs - resize running jobs (currently a gap) |
| [trainer#3015](https://github.com/kubeflow/trainer/issues/3015) | Workload-Aware Scheduling - native gang scheduling post K8s v1.36 |
| [trainer#3264](https://github.com/kubeflow/trainer/issues/3264) | Multi-Node NVLink support |
| [kueue#9046](https://github.com/kubernetes-sigs/kueue/issues/9046) | Multi-layer topology constraints for GB200 architectures |
| [kueue#3759](https://github.com/kubernetes-sigs/kueue/issues/3759) | Hierarchical cohorts with fair sharing |