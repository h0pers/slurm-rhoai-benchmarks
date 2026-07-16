# /// script
# requires-python = ">=3.12"
# dependencies = ["rich"]
# ///
"""Export knowledge base files for NotebookLM upload.

Copies docs, extracts notebook markdown, and summarizes benchmark
results into a flat directory ready to drag into NotebookLM.

Usage:
    uv run scripts/export_knowledge.py
"""

import json
import shutil
from pathlib import Path

from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = REPO_ROOT / "export"

console = Console()


def export_docs() -> list[Path]:
    """Copy all markdown docs except the Sphinx index page."""
    exported = []
    for src in sorted((REPO_ROOT / "docs").glob("*.md")):
        if src.name == "index.md":
            continue
        dst = EXPORT_DIR / src.name
        shutil.copy(src, dst)
        exported.append(dst)
    return exported


def export_notebook_markdown() -> list[Path]:
    """Extract markdown cells from documentation-only notebooks."""
    exported = []
    for nb_path in sorted((REPO_ROOT / "notebooks").glob("*.ipynb")):
        nb = json.loads(nb_path.read_text())
        cells = [cell for cell in nb["cells"] if cell["cell_type"] == "markdown"]
        if not cells:
            continue
        has_code = any(c["cell_type"] == "code" for c in nb["cells"])
        if has_code:
            continue
        parts = ["".join(cell["source"]) for cell in cells]
        stem = nb_path.stem.lstrip("0123456789-")
        dst = EXPORT_DIR / f"{stem}.md"
        dst.write_text("\n\n".join(parts) + "\n")
        exported.append(dst)
    return exported


def export_results() -> list[Path]:
    """One summary file per scenario with durations and metrics from each run."""
    results_dir = REPO_ROOT / "results"
    if not results_dir.exists():
        return []
    exported = []
    for scenario_dir in sorted(results_dir.iterdir()):
        if not scenario_dir.is_dir():
            continue
        lines = [f"# Benchmark results: {scenario_dir.name}\n"]
        for run_dir in sorted(scenario_dir.iterdir()):
            result_path = run_dir / "result.json"
            if not result_path.exists():
                continue
            r = json.loads(result_path.read_text())
            lines.append(f"## Run: {run_dir.name}")
            lines.append(f"Passed: {r['passed']}")
            lines.append(f"Durations: {json.dumps(r.get('durations_s', {}))}")
            lines.append(f"Metrics: {json.dumps(r.get('metrics', {}))}")
            failures = r.get("failures", [])
            if failures:
                lines.append(f"Failures: {failures}")
            lines.append("")
        dst = EXPORT_DIR / f"results-{scenario_dir.name}.md"
        dst.write_text("\n".join(lines))
        exported.append(dst)
    return exported


def main() -> None:
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
    EXPORT_DIR.mkdir()

    files = export_docs() + export_notebook_markdown() + export_results()

    console.print(f"Exported {len(files)} files to export/\n")
    for f in sorted(files):
        console.print(f"  {f.name}", style="cyan")


if __name__ == "__main__":
    main()
