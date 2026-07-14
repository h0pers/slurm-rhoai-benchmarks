# Runbook

How to set up, run, and tear down the benchmarks. For what the
benchmarks are and why, see [Methodology](methodology.md).

## Prerequisites

| Requirement | Check |
|---|---|
| Python >= 3.12 + [uv](https://docs.astral.sh/uv/) | `uv --version` |
| `oc` logged in to the target cluster | `oc whoami` |
| RHOAI 3.4.x with Trainer v2 + Kueue 1.3.x | `oc get clustertrainingruntime torch-distributed` |
| 2 GPU nodes (8 GPUs total) | `oc get nodes -l nvidia.com/gpu.present=true` |

Install the project:

```bash
uv sync
```

## One-time cluster setup

```bash
oc apply -f manifests/
```

This creates:

| Resource | Purpose |
|---|---|
| namespace `slurm-bench` | all jobs run here. Kueue auto-creates a `default` LocalQueue |
| ClusterQueue `bench-cq` | isolated queue for scenarios 5-6 with preemption enabled |
| LocalQueue `bench-queue` | entry point to `bench-cq` |
| WorkloadPriorityClass `bench-high` / `bench-low` | priorities for the preemption scenario |
| PVC `bench-checkpoints` (20Gi RWX) | shared checkpoint volume for fault-tolerance |

**Note:** `bench-cq` quotas cover the same physical GPUs as the
`default` queue. Do not run scenarios 5-6 while other GPU workloads are
active.

### Increase shared memory for multi-node jobs

Multi-node training crashes with `No space left on device` on
`/dev/shm`. Kubernetes gives each pod 64 MB of shared memory by default,
but PyTorch needs more when GPUs talk across nodes.

Run this once before multi-node scenarios (3, 4):

```bash
oc patch clustertrainingruntime torch-distributed --type=json -p '[
  {"op": "add",
   "path": "/spec/template/spec/replicatedJobs/0/template/spec/template/spec/volumes",
   "value": [{"name": "dshm", "emptyDir": {"medium": "Memory", "sizeLimit": "2Gi"}}]},
  {"op": "add",
   "path": "/spec/template/spec/replicatedJobs/0/template/spec/template/spec/containers/0/volumeMounts",
   "value": [{"name": "dshm", "mountPath": "/dev/shm"}]}
]'
```

Single-node scenarios (1, 2) are not affected.

### Provide the shared checkpoint volume

The fault-tolerant scenario (4) saves checkpoints to a shared disk (the
`bench-checkpoints` PVC) at `/mnt/checkpoints`. The disk must be attached
to the pods, or training fails the moment it tries to save.

Attach it on the runtime, not per job. The SDK's per-job way of attaching
it is silently dropped on this cluster, so the disk never shows up.
Patching the runtime (like `/dev/shm` above) always works.

Run this once before the fault-tolerant scenario (4):

```bash
oc patch clustertrainingruntime torch-distributed --type=json -p '[
  {"op": "add",
   "path": "/spec/template/spec/replicatedJobs/0/template/spec/template/spec/volumes/-",
   "value": {"name": "checkpoints", "persistentVolumeClaim": {"claimName": "bench-checkpoints"}}},
  {"op": "add",
   "path": "/spec/template/spec/replicatedJobs/0/template/spec/template/spec/containers/0/volumeMounts/-",
   "value": {"name": "checkpoints", "mountPath": "/mnt/checkpoints"}}
]'
```

Other scenarios mount the disk too but never write to it, so this is
safe. `oc apply -f manifests/` creates the PVC.

### Enable synchronized restarts for fault-tolerant training

When a worker pod dies during distributed training, all other ranks
crash too. By default, Kubernetes restarts each container independently
with increasing delays (CrashLoopBackOff). The pods never start at the
same time, so they can never reconnect.

The fix uses two settings that work together:

- `backoffLimit: 0` - instead of retrying inside the same pod, fail
  the Job immediately
- `failurePolicy.maxRestarts: 3` - when a Job fails, recreate all
  pods at once so they start together

```bash
oc patch clustertrainingruntime torch-distributed --type=json -p '[
  {"op": "add",
   "path": "/spec/template/spec/replicatedJobs/0/template/spec/backoffLimit",
   "value": 0}
]'

oc patch clustertrainingruntime torch-distributed --type=json -p '[
  {"op": "add",
   "path": "/spec/template/spec/failurePolicy",
   "value": {"maxRestarts": 3}}
]'
```

This is safe for all scenarios. Normal training that completes without
errors is not affected. The `maxRestarts` limit prevents infinite loops
if there is a real bug in the training code.

## Running a scenario

List available scenarios:

```bash
uv run bench scenarios
```

### CLI

```bash
uv run bench run single-gpu                # 1 rep (default from YAML)
uv run bench run single-gpu -r 3           # 3 repetitions
uv run bench run single-gpu --timeout 600  # override timeout
uv run bench run single-gpu --dry-run      # validate without submitting
```

### Notebooks

Each notebook under `notebooks/` calls the CLI in a single cell.
Run with **Restart Kernel & Run All** for counted runs.

Headless execution:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/1-single-gpu.ipynb
```

**Typical duration:** scenarios 1-4 take 5-15 min (training is short
but pod startup adds time). Scenarios 5-6 take 5-10 min (no training,
only queue behavior).

## Outputs

Every run writes to `results/<scenario>/<timestamp>/`:

- `result.json` - verdict, phase timestamps, metrics, config hash
- `events.json` - cluster events during the run
- `logs/<pod>.log` - full trainer logs per pod

Aggregate all runs:

```bash
uv run bench report             # terminal table
uv run bench report --markdown  # paste-ready for documents
```

## Configuration

Override defaults via environment variables or `.env` at project root:

| Variable | Default | Meaning |
|---|---|---|
| `BENCH_NAMESPACE` | `slurm-bench` | namespace for jobs |
| `BENCH_RESULTS_DIR` | `results/` | artifact output root |
| `BENCH_REPETITIONS` | `3` | default repetition count |
| `BENCH_POLL_INTERVAL_S` | `5` | status poll interval |

## Troubleshooting

**Pod in `CrashLoopBackOff`** - Check `oc logs -n slurm-bench <pod>`.
Look for pip install errors at the top of the log.

**Job stuck `Pending`** - Run `oc get workload -n slurm-bench`. Another
job likely holds the quota.

**Workload Admitted but pod stays `Pending`** - An external workload
holds physical GPUs. Find it:
`oc get pods -A -o json | grep -B5 nvidia.com/gpu`.

**GPU utilization empty in `result.json`** - The Thanos query failed.
The `error` field in `metrics` has the reason. The run is still valid.

**CLI run hangs** - Every watch loop respects `timeout_s`. If reached,
the run records the timeout as a failure.

## Teardown

```bash
oc delete -f manifests/
```

TrainJobs are cleaned up by the CLI after each run. Anything left over
is removed with the namespace.