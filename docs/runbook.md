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