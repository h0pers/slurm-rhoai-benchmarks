"""Sphinx configuration for the benchmark documentation site."""

project = "Slurm-to-RHOAI Benchmarks"
author = "Dmytro Hryshchenko"

extensions = ["myst_nb"]

# Render the committed notebook outputs as-is: the CI builder has no
# cluster access, and the outputs ARE the run evidence.
nb_execution_mode = "off"

myst_enable_extensions = ["colon_fence"]

html_theme = "sphinx_rtd_theme"
html_title = "Slurm-to-RHOAI Benchmarks"

exclude_patterns = ["_build", "jupyter_execute"]
