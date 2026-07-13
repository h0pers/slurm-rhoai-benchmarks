"""bench report - aggregate benchmark results."""

import json

import typer
from rich.table import Table

from bench.config import settings


def report(
    markdown: bool = typer.Option(False, help="Print a Markdown table instead of a rich one."),
) -> None:
    """Aggregate all results/<scenario>/<run>/result.json files into one table."""
    from bench.cli import console

    rows = []
    for path in sorted(settings.results_dir.glob("*/*/result.json")):
        result = json.loads(path.read_text())
        durations = result.get("durations_s", {})
        metrics = result.get("metrics", {})
        rows.append(
            (
                result["scenario"],
                result["run_id"],
                "PASS" if result["passed"] else "FAIL",
                str(durations.get("queue", "")),
                str(durations.get("startup", "")),
                str(durations.get("total", "")),
                str(metrics.get("train_samples_per_second", "")),
                str(metrics.get("mean_pct", "")),
            )
        )
    headers = (
        "scenario",
        "run",
        "verdict",
        "queue_s",
        "startup_s",
        "total_s",
        "samples/s",
        "gpu_util_%",
    )

    if not rows:
        console.print(f"no results under {settings.results_dir}")
        return
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
