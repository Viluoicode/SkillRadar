"""Bronze layer — land raw payloads exactly as fetched, never transformed, replayable.

One Parquet file per run holds the verbatim JSON for each posting plus provenance
(source, board token, source job id, fetched_at, run_id)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from ..common.logging import get_logger
from ..common.models import FetchedJob

logger = get_logger(__name__)


def land_bronze(
    fetched: list[FetchedJob],
    run_id: str,
    fetched_at: datetime,
    bronze_dir: str | Path,
) -> Path:
    """Write all fetched raw payloads for this run to a Parquet file; return its path."""
    bronze_dir = Path(bronze_dir)
    bronze_dir.mkdir(parents=True, exist_ok=True)
    out_path = bronze_dir / f"run_{run_id}.parquet"

    rows = [
        {
            "source": job.source.value,
            "board_token": job.board_token,
            "source_job_id": job.source_job_id,
            "raw_json": job.raw_json,
            "fetched_at": fetched_at,
            "run_id": run_id,
        }
        for job in fetched
    ]
    # An empty frame with the right columns still writes a valid (empty) Parquet file.
    df = pd.DataFrame(
        rows,
        columns=["source", "board_token", "source_job_id", "raw_json", "fetched_at", "run_id"],
    )
    df.to_parquet(out_path, index=False)
    logger.info("Bronze: wrote %d raw payloads to %s", len(rows), out_path.name)
    return out_path
