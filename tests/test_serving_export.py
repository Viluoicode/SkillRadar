"""export_serving_db copies every table into a fresh file with descriptions blanked — the slim,
committable DB the hosted dashboard serves. Driven through the real warehouse schema on a tmp DB."""

from datetime import UTC, datetime

import pytest

from skillradar.infrastructure.db.maintenance import export_serving_db
from skillradar.infrastructure.db.warehouse import connect, ensure_schema

NOW = datetime(2026, 6, 21, tzinfo=UTC)


def _seed(con) -> None:
    ensure_schema(con)
    con.execute(
        "INSERT INTO jobs (job_id, source, source_job_id, board_token, company, title, location, "
        "is_remote, description, apply_url, posted_at, dedup_hash, first_seen_at, last_seen_at, "
        "is_active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            "j1", "greenhouse", "s1", "acme", "Acme", "Data Engineer", "Remote",
            True, "a long job description " * 200, "https://acme.example/job", NOW,
            "h1", NOW, NOW, True,
        ],
    )
    con.execute("INSERT INTO job_skills VALUES ('j1', 'Python', 'Language')")
    con.execute(
        "INSERT INTO skill_demand VALUES "
        "('Data Engineer', 'Python', 'Language', 1, DATE '2026-06-21')"
    )
    con.execute(
        "INSERT INTO skill_trends VALUES ('Data Engineer', 'Python', DATE '2026-06-21', 1)"
    )
    con.execute("INSERT INTO ingestion_runs (run_id, started_at) VALUES ('r1', ?)", [NOW])


def test_export_copies_rows_and_blanks_descriptions(tmp_path):
    src = tmp_path / "full.duckdb"
    con = connect(src)
    _seed(con)
    con.close()

    dst = export_serving_db(src, tmp_path / "serving.duckdb")
    assert dst.exists()

    out = connect(dst, read_only=True)
    try:
        for table in ("jobs", "job_skills", "skill_demand", "skill_trends", "ingestion_runs"):
            assert out.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 1
        title, desc, apply_url = out.execute(
            "SELECT title, description, apply_url FROM jobs"
        ).fetchone()
        assert title == "Data Engineer"  # non-description columns preserved
        assert apply_url == "https://acme.example/job"
        assert desc == ""  # description blanked for the serving copy
    finally:
        out.close()


def test_export_is_rerunnable(tmp_path):
    src = tmp_path / "full.duckdb"
    con = connect(src)
    _seed(con)
    con.close()

    target = tmp_path / "serving.duckdb"
    export_serving_db(src, target)
    dst = export_serving_db(src, target)  # overwriting an existing file must not raise

    out = connect(dst, read_only=True)
    try:
        assert out.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    finally:
        out.close()


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_serving_db(tmp_path / "nope.duckdb", tmp_path / "serving.duckdb")
