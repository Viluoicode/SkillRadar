"""Run the dbt Gold transform (Silver → star schema → Gold marts) as a subprocess.

This is the production Gold builder for the cutover: the Python pipeline writes Silver + skills,
then dbt builds Gold. We *shell out* rather than import dbt because dbt-core has no Python 3.14
wheels yet, so it commonly runs from a separate interpreter / virtualenv (and DuckDB is
single-writer, so dbt must run only after the pipeline closes its write connection).

The warehouse target mirrors :func:`skillradar.infrastructure.config.data_target`: MotherDuck
(``prod``) when ``MOTHERDUCK_TOKEN`` is set, otherwise the local DuckDB file (``dev``).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# runner.py → dbt → infrastructure → skillradar → src → repo root, then transform/.
TRANSFORM_DIR = Path(__file__).resolve().parents[4] / "transform"


def _default_dbt_exe() -> str:
    """The dbt executable to invoke. ``SKILLRADAR_DBT_EXE`` lets prod/CI point at an isolated dbt
    env (dbt-core has no Python 3.14 wheels, and isolating it avoids clashing with the app's deps);
    otherwise the plain ``dbt`` on PATH is used."""
    return os.environ.get("SKILLRADAR_DBT_EXE", "dbt")


def dbt_available(transform_dir: Path = TRANSFORM_DIR) -> bool:
    """True when a dbt executable is resolvable and the project exists — i.e. dbt Gold is usable."""
    return shutil.which(_default_dbt_exe()) is not None and (
        transform_dir / "dbt_project.yml"
    ).exists()


def run_dbt_gold(
    duckdb_path: str | Path | None,
    snapshot_date: date,
    *,
    full_refresh: bool = False,
    transform_dir: Path = TRANSFORM_DIR,
    dbt_executable: str | None = None,
) -> None:
    """Build (and test) the dbt Gold layer for one daily snapshot. Raises on dbt failure.

    ``duckdb_path`` is the local warehouse file for the ``dev`` target; when ``MOTHERDUCK_TOKEN`` is
    set the ``prod`` (MotherDuck) target is used and this path is ignored. ``snapshot_date`` is
    passed through as a dbt var so dbt and the Python fallback stamp the same snapshot.
    """
    dbt_executable = dbt_executable or _default_dbt_exe()
    env = os.environ.copy()
    # Keep dbt's console logger from choking on non-ASCII paths (e.g. Windows + Unicode dirs).
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    use_motherduck = bool(env.get("MOTHERDUCK_TOKEN"))
    target = "prod" if use_motherduck else "dev"
    if not use_motherduck and duckdb_path is not None:
        env["SKILLRADAR_DUCKDB"] = str(Path(duckdb_path).resolve())

    project = ["--project-dir", str(transform_dir), "--profiles-dir", str(transform_dir)]
    build = [
        dbt_executable, "build", *project,
        "--target", target,
        "--vars", f"{{snapshot_date: '{snapshot_date.isoformat()}'}}",
    ]
    if full_refresh:
        build.append("--full-refresh")

    logger.info(
        "dbt Gold: deps + build (target=%s, snapshot=%s, full_refresh=%s)",
        target, snapshot_date.isoformat(), full_refresh,
    )
    # `dbt deps` is idempotent; ensure dbt_utils is installed before building.
    subprocess.run([dbt_executable, "deps", *project], check=True, env=env)
    subprocess.run(build, check=True, env=env)
