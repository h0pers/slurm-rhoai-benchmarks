"""bench scenarios - list the bundled benchmark scenarios."""

from rich.table import Table

from bench.schemas import load_all


def scenarios() -> None:
    """List the bundled benchmark scenarios."""
    from bench.cli import console

    table = Table("class", "name", "kind", "queue", "description")
    for scenario in load_all():
        table.add_row(
            str(scenario.workload_class),
            scenario.name,
            scenario.kind,
            scenario.queue,
            scenario.description,
        )
    console.print(table)
