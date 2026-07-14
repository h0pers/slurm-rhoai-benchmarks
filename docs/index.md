# Slurm-to-RHOAI Benchmarks

Reproducible benchmarks comparing Kubeflow Trainer v2 + Kueue on Red
Hat OpenShift AI against Slurm 26.05 as a documented baseline.

- **[Methodology](methodology.md)** - what we test and why
- **[Scenarios](scenarios.md)** - the seven workload classes
- **[Metrics](metrics.md)** - what is measured
- **[Runbook](runbook.md)** - how to run

```{toctree}
:maxdepth: 1
:hidden:

methodology
scenarios
metrics
runbook
```

```{toctree}
:maxdepth: 1
:caption: Benchmarks

notebooks/1-single-gpu
notebooks/2-multi-gpu-ddp
notebooks/3-multi-node
notebooks/4-fault-tolerant
notebooks/5-gang-scheduling
notebooks/6-queue-priority
notebooks/7-hpc-math
results
next-steps
```