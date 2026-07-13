"""Gang scheduling scenario flow (workload class 5)."""

import time
from pathlib import Path
from typing import Any

from rich.console import Console

from bench.config import settings
from bench.runner import artifacts, criteria, jobs, kube
from bench.schemas import GangScenario
from bench.utils import utcnow


def run_gang(
    scenario: GangScenario,
    run_dir: Path,
    console: Console,
    log_fn: Any,
    log_phases_fn: Any,
) -> tuple[bool, list[str], dict[str, Any], dict[str, Any]]:
    blocker = jobs.submit_hold(scenario.blocker, scenario, "blocker")
    log_fn(console, "Blocker submitted", blocker)

    deadline = time.monotonic() + scenario.timeout_s
    _wait_for_pods(blocker, scenario.blocker.nodes, deadline, console, "Blocker running", log_fn)

    measured = jobs.submit_hold(scenario.measured, scenario, "measured")
    timestamps: dict[str, Any] = {"submitted": utcnow()}
    log_fn(console, "Measured submitted", measured)

    pods_while_blocked = 0
    while time.monotonic() < deadline:
        done = kube.job_condition(blocker, "Complete")
        if done:
            timestamps["blocker_completed"] = done
            log_fn(console, "Blocker completed", "")
            break
        pods_while_blocked = max(pods_while_blocked, len(kube.pods_of(measured)))
        time.sleep(settings.poll_interval_s)

    logged: set[str] = set()
    while time.monotonic() < deadline:
        jobs.observe(measured, scenario.measured.nodes, timestamps)
        log_phases_fn(console, timestamps, logged)
        if "completed" in timestamps or "failed" in timestamps:
            break
        time.sleep(settings.poll_interval_s)

    run_metrics: dict[str, Any] = {
        "pods_while_blocked": pods_while_blocked,
        "admission_latency_s": (
            jobs.seconds_between(
                timestamps.get("blocker_completed", ""), timestamps.get("admitted", "")
            )
            if "blocker_completed" in timestamps and "admitted" in timestamps
            else None
        ),
        "gang_start_spread_s": timestamps.pop("gang_start_spread_s", None),
    }

    _save_logs(blocker, run_dir)
    _save_logs(measured, run_dir)

    failures = criteria.evaluate(scenario.checks, timestamps, run_metrics, scenario)
    kube.delete_trainjob(blocker)
    kube.delete_trainjob(measured)
    jobs.finalize(scenario, timestamps, run_metrics, failures, run_dir)

    return not failures, failures, timestamps, run_metrics


def _save_logs(job: str, run_dir: Path) -> None:
    for pod_name, log in kube.pod_logs(job).items():
        artifacts.write_log(run_dir, pod_name, log)


def _wait_for_pods(
    job: str,
    expected: int,
    deadline: float,
    console: Console,
    message: str,
    log_fn: Any,
) -> None:
    while time.monotonic() < deadline:
        if len(kube.pod_start_times(job)) == expected:
            log_fn(console, message, "")
            return
        time.sleep(settings.poll_interval_s)
