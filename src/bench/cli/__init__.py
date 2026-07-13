import typer
from rich.console import Console

from bench.cli.report import report
from bench.cli.run import run
from bench.cli.scenarios import scenarios

app = typer.Typer(help="Slurm-to-RHOAI benchmark harness.")
console = Console()

app.command()(run)
app.command()(scenarios)
app.command()(report)
