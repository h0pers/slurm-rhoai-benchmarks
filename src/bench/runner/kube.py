"""Thin facade over the Kubernetes API - all cluster reads/writes live here.

Each function answers exactly one question about a benchmark job (or
performs one action on it). No benchmark logic: the scenario notebooks
and jobs.py compose these into flows. Timestamps returned are the
server-side ones stored on the objects themselves (condition
lastTransitionTime, container startedAt), formatted as ISO-8601 UTC
strings.
"""

import contextlib
from functools import cache

from kubernetes import client, config

from bench.config import settings
from bench.utils import utcnow

TRAINER_GROUP = "trainer.kubeflow.org"
TRAINER_VERSION = "v1alpha1"
KUEUE_GROUP = "kueue.x-k8s.io"
KUEUE_VERSION = "v1beta1"
JOBSET_LABEL = "jobset.sigs.k8s.io/jobset-name"
ISO = "%Y-%m-%dT%H:%M:%SZ"


@cache
def _core() -> client.CoreV1Api:
    config.load_kube_config()
    return client.CoreV1Api()


@cache
def _custom() -> client.CustomObjectsApi:
    config.load_kube_config()
    return client.CustomObjectsApi()


def pods_of(job_name: str) -> list:
    """All pods belonging to one TrainJob, sorted by name."""
    pods = (
        _core()
        .list_namespaced_pod(settings.namespace, label_selector=JOBSET_LABEL + "=" + job_name)
        .items
    )
    return sorted(pods, key=lambda pod: pod.metadata.name)


def pod_nodes(job_name: str) -> list[str]:
    """Names of the nodes the job's pods are (or were) scheduled on."""
    return sorted({pod.spec.node_name for pod in pods_of(job_name) if pod.spec.node_name})


def pod_start_times(job_name: str) -> list[str]:
    """startedAt of the trainer container for every currently running pod."""
    started = []
    for pod in pods_of(job_name):
        for status in pod.status.container_statuses or []:
            if status.state.running:
                started.append(status.state.running.started_at.strftime(ISO))
    return started


def job_condition(job_name: str, condition_type: str) -> str | None:
    """lastTransitionTime of a TrainJob condition (e.g. Complete), if True."""
    try:
        job = _custom().get_namespaced_custom_object(
            TRAINER_GROUP, TRAINER_VERSION, settings.namespace, "trainjobs", job_name
        )
    except client.ApiException:
        return None
    return _condition_time(job.get("status", {}), condition_type)


def workload_condition(job_name: str, condition_type: str) -> str | None:
    """lastTransitionTime of a Kueue Workload condition (e.g. Admitted, Evicted).

    The Workload is found by its ownerReference back to the TrainJob.
    """
    workloads = _custom().list_namespaced_custom_object(
        KUEUE_GROUP, KUEUE_VERSION, settings.namespace, "workloads"
    )["items"]
    for workload in workloads:
        owners = workload["metadata"].get("ownerReferences", [])
        if any(owner["name"] == job_name for owner in owners):
            return _condition_time(workload.get("status", {}), condition_type)
    return None


def pod_logs(job_name: str) -> dict[str, str]:
    """Trainer-container logs per pod name."""
    logs = {}
    for pod in pods_of(job_name):
        try:
            logs[pod.metadata.name] = _core().read_namespaced_pod_log(
                pod.metadata.name, settings.namespace, container="node"
            )
        except client.ApiException as error:
            logs[pod.metadata.name] = f"<log collection failed: {error.reason}>"
    return logs


def delete_worker_pod(job_name: str, worker_index: int) -> str:
    """Kill one worker pod (fault injection); returns the kill timestamp."""
    pods = pods_of(job_name)
    if worker_index >= len(pods):
        raise RuntimeError(f"job {job_name} has {len(pods)} pods, no index {worker_index}")
    _core().delete_namespaced_pod(
        pods[worker_index].metadata.name, settings.namespace, grace_period_seconds=0
    )
    return utcnow()


def newest_pod_created_after(job_name: str, timestamp: str) -> bool:
    """True if a replacement pod (created after `timestamp`) exists."""
    return any(
        pod.metadata.creation_timestamp.strftime(ISO) > timestamp for pod in pods_of(job_name)
    )


def delete_trainjob(job_name: str) -> None:
    with contextlib.suppress(client.ApiException):
        _custom().delete_namespaced_custom_object(
            TRAINER_GROUP, TRAINER_VERSION, settings.namespace, "trainjobs", job_name
        )


def events(name_prefix: str) -> list[dict]:
    """Namespace events for objects whose name starts with the prefix."""
    return [
        {
            "time": str(event.last_timestamp or event.event_time),
            "object": f"{event.involved_object.kind}/{event.involved_object.name}",
            "reason": event.reason,
            "message": event.message,
        }
        for event in _core().list_namespaced_event(settings.namespace).items
        if (event.involved_object.name or "").startswith(name_prefix)
    ]


def server_version() -> str:
    config.load_kube_config()
    return client.VersionApi().get_code().git_version


def _condition_time(status: dict, condition_type: str) -> str | None:
    for condition in status.get("conditions", []):
        if condition["type"] == condition_type and condition["status"] == "True":
            return condition["lastTransitionTime"]
    return None
