"""Shared job steps used by the scenario notebooks.

Notebooks own the flow (submit -> watch loop -> verdict, one step per
cell); this module owns the mechanics of each step. All cluster access
goes through kube.py, all SDK access happens here.
"""

from datetime import UTC, datetime
from pathlib import Path

from kubeflow.trainer import CustomTrainer, KubernetesBackendConfig, TrainerClient
from kubeflow.trainer.options import Labels, Name

from bench.config import settings
from bench.runner import artifacts, kube, metrics
from bench.schemas import GangScenario, JobShape, PreemptionScenario, TrainScenario
from bench.train.workload import hold_func, train_func
from bench.utils import durations, utcnow

QUEUE_LABEL = "kueue.x-k8s.io/queue-name"
PRIORITY_LABEL = "kueue.x-k8s.io/priority-class"
TRAIN_PACKAGES = ["transformers", "datasets", "accelerate"]

Scenario = TrainScenario | GangScenario | PreemptionScenario


def submit_train(scenario: TrainScenario) -> str:
    """Create the TrainJob for a training scenario; returns the job name."""
    job = _job_name(scenario.name)
    func_args = scenario.training.model_dump()
    options = [Name(job), Labels({QUEUE_LABEL: scenario.queue})]
    if scenario.checkpoint:
        # The checkpoint PVC is mounted by the ClusterTrainingRuntime itself
        # (see runbook: "Provide the shared checkpoint volume"). The SDK's
        # RuntimePatch cannot mount it here: SDK 0.4.x serializes patches into
        # spec.runtimePatches, a field the cluster's v1alpha1 TrainJob CRD does
        # not have, so Kubernetes silently prunes it and the volume never lands.
        func_args["checkpoint_dir"] = scenario.checkpoint.mount_path + "/" + job
        func_args["save_steps"] = scenario.checkpoint.save_steps
    trainer = CustomTrainer(
        func=train_func,
        func_args=func_args,
        num_nodes=scenario.nodes,
        resources_per_node=dict(scenario.resources_per_node),
        packages_to_install=TRAIN_PACKAGES,
    )
    _client().train(runtime=scenario.runtime, trainer=trainer, options=options)
    return job


def submit_hold(shape: JobShape, scenario: Scenario, role: str) -> str:
    """Create a GPU-holding job (gang/preemption scenarios); returns the job name."""
    job = _job_name(role)
    labels = {QUEUE_LABEL: scenario.queue}
    if shape.priority_class:
        labels[PRIORITY_LABEL] = shape.priority_class
    trainer = CustomTrainer(
        func=hold_func,
        func_args={"hold_s": shape.hold_s},
        num_nodes=shape.nodes,
        resources_per_node=dict(shape.resources_per_node),
    )
    _client().train(runtime=scenario.runtime, trainer=trainer, options=[Name(job), Labels(labels)])
    return job


def observe(job: str, expected_pods: int, timestamps: dict) -> dict:
    """One status snapshot: record admitted / pods_running / completed / failed.

    Each timestamp is written once, from server-side object state. Returns
    the dict so the watch cell can display progress.
    """
    if "admitted" not in timestamps:
        admitted = kube.workload_condition(job, "Admitted")
        if admitted:
            timestamps["admitted"] = admitted
    if "pods_running" not in timestamps:
        started = kube.pod_start_times(job)
        if len(started) == expected_pods:
            timestamps["pods_running"] = max(started)
            timestamps["gang_start_spread_s"] = seconds_between(min(started), max(started))
    for condition, key in (("Complete", "completed"), ("Failed", "failed")):
        if key not in timestamps:
            when = kube.job_condition(job, condition)
            if when:
                timestamps[key] = when
    return timestamps


def collect(scenario: TrainScenario, job: str, timestamps: dict, run_dir: Path) -> dict:
    """Save pod logs, parse [BENCH] markers, query GPU utilization."""
    run_metrics = {}
    for pod_name, log in kube.pod_logs(job).items():
        artifacts.write_log(run_dir, pod_name, log)
        run_metrics.update(metrics.parse_markers(log).model_dump(exclude_none=True))
    if "pods_running" in timestamps:
        gpu_count = int(scenario.resources_per_node.get("nvidia.com/gpu", 0)) * scenario.nodes
        gpu = metrics.gpu_utilization(
            kube.pod_nodes(job),
            gpu_count,
            timestamps["pods_running"],
            timestamps.get("completed", utcnow()),
        )
        run_metrics.update(gpu.model_dump(exclude_none=True))
    if "gang_start_spread_s" in timestamps:
        run_metrics["gang_start_spread_s"] = timestamps.pop("gang_start_spread_s")
    return run_metrics


def finalize(
    scenario: Scenario, timestamps: dict, run_metrics: dict, failures: list, run_dir: Path
) -> Path:
    """Write events.json and result.json."""
    artifacts.write_events(run_dir, kube.events("bench-"))
    return artifacts.write_result(
        run_dir,
        config=scenario.model_dump(),
        versions={
            "sdk": _sdk_version(),
            "runtime": scenario.runtime,
            "kubernetes": kube.server_version(),
        },
        timestamps=timestamps,
        metrics=run_metrics,
        passed=not failures,
        failures=failures,
    )


def seconds_between(earlier: str, later: str) -> float:
    return durations({"a": earlier, "b": later}, {"d": ("a", "b")}).get("d", 0.0)


def _client() -> TrainerClient:
    return TrainerClient(backend_config=KubernetesBackendConfig(namespace=settings.namespace))


def _job_name(prefix: str) -> str:
    return "bench-" + prefix + "-" + datetime.now(UTC).strftime("%H%M%S")


def _sdk_version() -> str:
    from importlib.metadata import version

    return version("kubeflow")
