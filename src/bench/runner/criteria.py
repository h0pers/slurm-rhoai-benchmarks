"""Data-driven pass criteria for benchmark scenarios.

Each check function receives (timestamps, metrics, scenario) and returns
None on success or a failure-message string. The scenario YAML lists
which checks apply via its `checks` field; evaluate() runs them in order.
"""

from collections.abc import Callable
from typing import Any

from bench.schemas import TrainScenario

Check = Callable[[dict[str, str], dict[str, Any], Any], str | None]


def _completed(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if "completed" not in timestamps:
        return "TrainJob did not reach Complete"
    return None


def _throughput_recorded(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if not metrics.get("train_samples_per_second"):
        return "no throughput marker found in logs"
    return None


def _gpu_util_positive(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if not metrics.get("mean_pct"):
        return "no GPU utilization observed"
    return None


def _world_size_matches(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    sc: TrainScenario = scenario
    expected = sc.nodes * int(sc.resources_per_node.get("nvidia.com/gpu", 0))
    actual = metrics.get("world_size")
    if actual != expected:
        return f"expected world_size={expected}, got {actual}"
    return None


def _resumed_from_checkpoint(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if not metrics.get("resumed_from_step"):
        return "no checkpoint resume detected after pod kill"
    return None


def _zero_pods_while_blocked(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    count = metrics.get("pods_while_blocked", 0)
    if count:
        return f"{count} pod(s) existed while blocker held GPUs (expected 0)"
    return None


def _low_evicted(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if "low_evicted" not in timestamps:
        return "low-priority workload was never evicted"
    return None


def _low_requeued(timestamps: dict, metrics: dict, scenario: Any) -> str | None:
    if "low_requeued" not in timestamps:
        return "low-priority workload not requeued after preemption"
    return None


REGISTRY: dict[str, Check] = {
    "completed": _completed,
    "throughput_recorded": _throughput_recorded,
    "gpu_util_positive": _gpu_util_positive,
    "world_size_matches": _world_size_matches,
    "resumed_from_checkpoint": _resumed_from_checkpoint,
    "zero_pods_while_blocked": _zero_pods_while_blocked,
    "low_evicted": _low_evicted,
    "low_requeued": _low_requeued,
}


def evaluate(
    checks: list[str],
    timestamps: dict[str, str],
    metrics: dict[str, Any],
    scenario: Any,
) -> list[str]:
    """Run named checks in order; return failure messages (empty = all passed)."""
    failures = []
    for name in checks:
        if name not in REGISTRY:
            raise ValueError(f"unknown check '{name}'; available: {sorted(REGISTRY)}")
        result = REGISTRY[name](timestamps, metrics, scenario)
        if result is not None:
            failures.append(result)
    return failures
