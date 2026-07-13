"""bench report - aggregate benchmark results."""

import json
import statistics

import typer
from rich.table import Table

from bench.config import settings
from bench.schemas import TrainScenario, load_all


def _load_results() -> list[dict]:
    rows = []
    for path in sorted(settings.results_dir.glob("*/*/result.json")):
        rows.append(json.loads(path.read_text()))
    return rows


def _scenario_configs() -> dict[str, TrainScenario]:
    return {s.name: s for s in load_all() if isinstance(s, TrainScenario)}


def _baseline_median_throughput(
    results: list[dict],
    baseline_name: str,
) -> float | None:
    values = [
        r["metrics"]["train_samples_per_second"]
        for r in results
        if r["scenario"] == baseline_name
        and r["passed"]
        and r["metrics"].get("train_samples_per_second") is not None
    ]
    return statistics.median(values) if values else None


def _scaling_efficiency(
    throughput: float | None,
    baseline_throughput: float | None,
    total_gpus: int,
) -> float | None:
    if throughput is None or baseline_throughput is None or baseline_throughput == 0:
        return None
    return round(throughput / (baseline_throughput * total_gpus), 3)


def _total_gpus(config: TrainScenario) -> int:
    return config.nodes * int(config.resources_per_node.get("nvidia.com/gpu", 1))


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return str(value)


def _median_or_none(values: list[float]) -> float | None:
    return round(statistics.median(values), 2) if values else None


def _build_detail_rows(
    results: list[dict],
    configs: dict[str, TrainScenario],
) -> list[tuple[str, ...]]:
    baseline_cache: dict[str, float | None] = {}
    rows = []
    for r in results:
        durations = r.get("durations_s", {})
        metrics = r.get("metrics", {})
        throughput = metrics.get("train_samples_per_second")

        scaling_eff = None
        cfg = configs.get(r["scenario"])
        if cfg and cfg.baseline_scenario:
            if cfg.baseline_scenario not in baseline_cache:
                baseline_cache[cfg.baseline_scenario] = _baseline_median_throughput(
                    results, cfg.baseline_scenario
                )
            scaling_eff = _scaling_efficiency(
                throughput, baseline_cache[cfg.baseline_scenario], _total_gpus(cfg)
            )

        rows.append(
            (
                r["scenario"],
                r["run_id"],
                "PASS" if r["passed"] else "FAIL",
                _fmt(durations.get("queue")),
                _fmt(durations.get("startup")),
                _fmt(durations.get("total")),
                _fmt(throughput),
                _fmt(metrics.get("mean_pct")),
                _fmt(scaling_eff),
            )
        )
    return rows


def _build_summary_rows(
    results: list[dict],
    configs: dict[str, TrainScenario],
) -> list[tuple[str, ...]]:
    groups: dict[str, list[dict]] = {}
    for r in results:
        groups.setdefault(r["scenario"], []).append(r)

    baseline_cache: dict[str, float | None] = {}
    rows = []
    for scenario_name, runs in groups.items():
        passed = sum(1 for r in runs if r["passed"])
        total = len(runs)

        queue_vals = [
            r["durations_s"]["queue"]
            for r in runs
            if r.get("durations_s", {}).get("queue") is not None
        ]
        startup_vals = [
            r["durations_s"]["startup"]
            for r in runs
            if r.get("durations_s", {}).get("startup") is not None
        ]
        total_vals = [
            r["durations_s"]["total"]
            for r in runs
            if r.get("durations_s", {}).get("total") is not None
        ]
        throughput_vals = [
            r["metrics"]["train_samples_per_second"]
            for r in runs
            if r.get("metrics", {}).get("train_samples_per_second") is not None
        ]
        gpu_vals = [
            r["metrics"]["mean_pct"]
            for r in runs
            if r.get("metrics", {}).get("mean_pct") is not None
        ]

        med_throughput = _median_or_none(throughput_vals)

        scaling_eff = None
        cfg = configs.get(scenario_name)
        if cfg and cfg.baseline_scenario:
            if cfg.baseline_scenario not in baseline_cache:
                baseline_cache[cfg.baseline_scenario] = _baseline_median_throughput(
                    results, cfg.baseline_scenario
                )
            scaling_eff = _scaling_efficiency(
                med_throughput, baseline_cache[cfg.baseline_scenario], _total_gpus(cfg)
            )

        rows.append(
            (
                scenario_name,
                f"{passed}/{total}",
                _fmt(_median_or_none(queue_vals)),
                _fmt(_median_or_none(startup_vals)),
                _fmt(_median_or_none(total_vals)),
                _fmt(med_throughput),
                _fmt(_median_or_none(gpu_vals)),
                _fmt(scaling_eff),
            )
        )
    return rows


DETAIL_HEADERS = (
    "scenario",
    "run",
    "verdict",
    "queue_s",
    "startup_s",
    "total_s",
    "samples/s",
    "gpu_util_%",
    "scaling_eff",
)
SUMMARY_HEADERS = (
    "scenario",
    "pass_rate",
    "queue_s",
    "startup_s",
    "total_s",
    "samples/s",
    "gpu_util_%",
    "scaling_eff",
)


def _print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]], markdown: bool) -> None:
    from bench.cli import console

    if markdown:
        print("| " + " | ".join(headers) + " |")
        print("|" + "---|" * len(headers))
        for row in rows:
            print("| " + " | ".join(row) + " |")
        return
    table = Table(*headers)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def report(
    detail: bool = typer.Option(
        False, help="Show individual runs instead of per-scenario medians."
    ),
    markdown: bool = typer.Option(False, help="Print a Markdown table instead of a rich one."),
) -> None:
    """Aggregate all results/<scenario>/<run>/result.json files into one table."""
    from bench.cli import console

    results = _load_results()
    if not results:
        console.print(f"no results under {settings.results_dir}")
        return

    configs = _scenario_configs()

    if detail:
        rows = _build_detail_rows(results, configs)
        _print_table(DETAIL_HEADERS, rows, markdown)
    else:
        rows = _build_summary_rows(results, configs)
        _print_table(SUMMARY_HEADERS, rows, markdown)
