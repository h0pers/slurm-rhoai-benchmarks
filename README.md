# slurm-rhoai-benchmarks

Reproducible benchmarks of **Kubeflow Trainer v2 + Kueue on Red Hat
OpenShift AI**, covering representative Slurm HPC workload classes.
Slurm 26.05 serves as a documented comparison baseline.

## Layout

| Path | Contents |
|---|---|
| `notebooks/` | one notebook per scenario - the way benchmarks run |
| `scenarios/` | YAML definitions for the six benchmark scenarios |
| `src/bench/` | CLI harness (submission, observation, metrics, artifacts) |
| `manifests/` | cluster resources applied once (`oc apply -f manifests/`) |
| `docs/` | methodology, runbook, metrics (Sphinx/MyST site) |
| `results/` | run artifacts: `result.json`, pod logs, events |

## Quickstart

```bash
uv sync                      # install harness + notebook tooling
oc login ...                 # cluster with RHOAI 3.4.x + Kueue 1.3.x + GPUs
oc apply -f manifests/       # one-time cluster setup
uv run bench scenarios       # list scenarios
uv run bench run single-gpu  # run a scenario
uv run bench report          # aggregate results
```

See `docs/runbook.md` for details and troubleshooting.