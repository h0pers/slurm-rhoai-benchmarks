"""Metric extraction: [BENCH] log markers and Prometheus GPU utilization."""

import statistics
import subprocess
from pathlib import Path
from urllib.parse import urlunparse

import requests
from pydantic import BaseModel

from bench.config import settings

MARKER = "[BENCH] "


class BenchMarkers(BaseModel):
    """Values the workload printed as `[BENCH] key=value` lines."""

    world_size: int | None = None
    train_runtime_s: float | None = None
    train_samples_per_second: float | None = None
    resumed_from_step: int | None = None
    hold_started_s: int | None = None
    hold_done: int | None = None


class GpuUtilization(BaseModel):
    """DCGM GPU utilization over one run's time window."""

    mean_pct: float | None = None
    max_pct: float | None = None
    gpu_count: int | None = None
    error: str | None = None


def parse_markers(log_text: str) -> BenchMarkers:
    """Extract `[BENCH] key=value` lines printed by the workload."""
    raw = {}
    for line in log_text.splitlines():
        if MARKER in line:
            key, _, value = line.split(MARKER, 1)[1].strip().partition("=")
            raw[key] = value
    known = {key: value for key, value in raw.items() if key in BenchMarkers.model_fields}
    return BenchMarkers.model_validate(known)


def _ingress_ca_bundle() -> Path | bool:
    """Path to the cluster ingress CA, fetched once and cached.

    OpenShift routes are signed by the cluster's ingress CA, published in
    the default-ingress-cert ConfigMap. Verifying against it keeps TLS
    verification on for self-managed clusters. Falls back to the system
    trust store (True) if the ConfigMap cannot be read.
    """
    cache = settings.results_dir / ".ingress-ca.crt"
    if cache.exists():
        return cache
    try:
        ca = subprocess.run(
            [
                "oc",
                "get",
                "configmap",
                "default-ingress-cert",
                "-n",
                "openshift-config-managed",
                "-o",
                "jsonpath={.data.ca-bundle\\.crt}",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        if not ca.strip():
            return True
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(ca)
        return cache
    except subprocess.CalledProcessError:
        return True


def gpu_utilization(nodes: list[str], gpu_count: int, start: str, end: str) -> GpuUtilization:
    """Mean/max DCGM GPU utilization (%) for one job's GPUs over a time window.

    The cluster's DCGM exporter labels series per physical GPU (node
    Hostname + gpu index) without workload-pod attribution, so we query
    the nodes the job ran on and keep the gpu_count busiest GPU series -
    on a benchmark cluster where the job is the only GPU consumer these
    are exactly the job's GPUs. Returns an error-carrying DTO when the
    query fails, so a monitoring hiccup never fails a benchmark run.
    """
    try:
        host = subprocess.run(
            [
                "oc",
                "get",
                "route",
                "thanos-querier",
                "-n",
                "openshift-monitoring",
                "-o",
                "jsonpath={.spec.host}",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        token = subprocess.run(
            ["oc", "whoami", "-t"], capture_output=True, text=True, check=True
        ).stdout.strip()

        url = urlunparse(("https", host, "/api/v1/query_range", "", "", ""))
        node_filter = "|".join(nodes)
        query = f'DCGM_FI_DEV_GPU_UTIL{{Hostname=~"{node_filter}"}}'
        verify = _ingress_ca_bundle()
        response = requests.get(
            url,
            params={"query": query, "start": start, "end": end, "step": "15s"},
            headers={"Authorization": "Bearer " + token},
            verify=str(verify) if isinstance(verify, Path) else verify,
            timeout=30,
        )
        response.raise_for_status()
        series = response.json()["data"]["result"]
    except (subprocess.CalledProcessError, requests.RequestException, KeyError) as error:
        return GpuUtilization(error=str(error))

    per_gpu = []
    for serie in series:
        values = [float(value) for _, value in serie["values"]]
        if values:
            per_gpu.append((statistics.mean(values), max(values)))
    busiest = sorted(per_gpu, reverse=True)[:gpu_count]
    if not busiest:
        return GpuUtilization()
    return GpuUtilization(
        mean_pct=round(statistics.mean(mean for mean, _ in busiest), 1),
        max_pct=round(max(peak for _, peak in busiest), 1),
        gpu_count=len(busiest),
    )
