"""Silver reconciliation rules — pure, no persistence.

Given the postings fetched this run and the jobs already on record, decide the new set of
job rows: dedupe by ``(source, source_job_id)``, skip cross-source duplicates by content
hash, and apply the lifecycle (``first_seen`` / ``last_seen`` / ``is_active``). A posting
is deactivated only when it vanished from a board that fetched successfully this run.

Port of the .NET ``NormalizeToSilverAsync``; the only difference is that loading/saving the
rows is delegated to a repository (see ``application.services.silver``)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from skillradar.domain.dedup import compute_dedup_hash, make_job_id
from skillradar.domain.models import FetchedJob
from skillradar.domain.records import JobRecord


@dataclass
class ReconcileResult:
    jobs: list[JobRecord]  # the full new state of the jobs table
    upserted: list[str]  # job_ids inserted or refreshed this run
    deactivated: int  # count of jobs flipped to inactive


def _apply_fields(rec: JobRecord, f: FetchedJob, dedup_hash: str, now: datetime) -> None:
    rec.board_token = f.board_token
    rec.source_job_id = f.source_job_id
    rec.company = f.company
    rec.title = f.title
    rec.location = f.location
    rec.is_remote = bool(f.remote)
    rec.description = f.description or ""
    rec.apply_url = f.apply_url or ""
    rec.posted_at = f.posted_at
    rec.dedup_hash = dedup_hash
    rec.last_seen_at = now
    rec.is_active = True


def reconcile_jobs(
    existing: list[JobRecord],
    fetched: list[FetchedJob],
    succeeded_boards: set[tuple[str, str]],
    now: datetime,
) -> ReconcileResult:
    jobs: dict[str, JobRecord] = {r.job_id: r for r in existing}
    by_source_id: dict[tuple[str, str], str] = {
        (r.source, r.source_job_id): r.job_id for r in existing
    }

    # Owner of each dedup hash among currently active jobs (for cross-source dedup).
    active_hash_owner: dict[str, tuple[str, str]] = {}
    for r in existing:
        if r.is_active:
            active_hash_owner.setdefault(r.dedup_hash, (r.source, r.source_job_id))

    seen_keys: set[tuple[str, str]] = set()
    upserted: list[str] = []

    for f in fetched:
        key = (f.source.value, f.source_job_id)
        if key in seen_keys:
            continue  # same posting appeared twice in this run
        seen_keys.add(key)

        dedup_hash = compute_dedup_hash(f.company, f.title, f.location)

        if key in by_source_id:
            jid = by_source_id[key]
            _apply_fields(jobs[jid], f, dedup_hash, now)
            active_hash_owner[dedup_hash] = key
            upserted.append(jid)
        else:
            owner = active_hash_owner.get(dedup_hash)
            if owner is not None and owner[0] != f.source.value:
                continue  # cross-source duplicate of an active job — skip
            jid = make_job_id(f.source.value, f.source_job_id)
            rec = JobRecord(
                job_id=jid,
                source=f.source.value,
                source_job_id=f.source_job_id,
                board_token=f.board_token,
                company=f.company,
                title=f.title,
                location=f.location,
                is_remote=bool(f.remote),
                description=f.description or "",
                apply_url=f.apply_url or "",
                posted_at=f.posted_at,
                dedup_hash=dedup_hash,
                first_seen_at=now,
                last_seen_at=now,
                is_active=True,
            )
            jobs[jid] = rec
            by_source_id[key] = jid
            active_hash_owner[dedup_hash] = key
            upserted.append(jid)

    # Deactivate postings that vanished from boards we successfully fetched.
    deactivated = 0
    for r in jobs.values():
        if not r.is_active:
            continue
        if (r.source, r.board_token) not in succeeded_boards:
            continue  # board failed or not in catalog — leave untouched
        if (r.source, r.source_job_id) not in seen_keys:
            r.is_active = False
            deactivated += 1

    return ReconcileResult(jobs=list(jobs.values()), upserted=upserted, deactivated=deactivated)
