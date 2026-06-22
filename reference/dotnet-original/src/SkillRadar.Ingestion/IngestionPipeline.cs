using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using SkillRadar.Core.Skills;
using SkillRadar.Core.Text;
using SkillRadar.Data;

namespace SkillRadar.Ingestion;

/// <summary>
/// Orchestrates the Medallion pipeline for one run:
/// Bronze (fetch + store raw) → Silver (normalize, dedupe, upsert) → Gold (extract skills,
/// aggregate demand). Each board is isolated: a failing board is logged and skipped without
/// aborting the run, and a board's existing jobs are only deactivated when that board fetched
/// successfully.
/// </summary>
public class IngestionPipeline(
    SkillRadarDbContext db,
    SourceCatalogProvider catalog,
    JobSourceRegistry registry,
    SkillExtractor skillExtractor,
    TimeProvider clock,
    IOptions<IngestionOptions> options,
    ILogger<IngestionPipeline> logger)
{
    public async Task<IngestionRun> RunAsync(string trigger, CancellationToken ct = default)
    {
        var now = clock.GetUtcNow();
        var run = new IngestionRun { StartedAt = now, Trigger = trigger, Status = IngestionRunStatus.Running };
        db.IngestionRuns.Add(run);
        await db.SaveChangesAsync(ct);

        var errors = new List<string>();
        var (fetched, succeededBoards) = await FetchAndStoreBronzeAsync(run, errors, ct);
        run.RawPostingsFetched = fetched.Count;
        run.BoardsSucceeded = succeededBoards.Count;

        var (upsertedJobIds, deactivated) = await NormalizeToSilverAsync(fetched, succeededBoards, now, ct);
        run.JobsUpserted = upsertedJobIds.Count;
        run.JobsDeactivated = deactivated;

        await ExtractAndAggregateAsync(upsertedJobIds, now, ct);

        run.FinishedAt = clock.GetUtcNow();
        run.Errors = errors.Count > 0 ? string.Join('\n', errors) : null;
        run.Status = errors.Count == 0
            ? IngestionRunStatus.Succeeded
            : (run.BoardsSucceeded > 0 ? IngestionRunStatus.CompletedWithErrors : IngestionRunStatus.Failed);
        await db.SaveChangesAsync(ct);

        logger.LogInformation(
            "Ingestion run {RunId} {Status}: {Boards}/{Attempted} boards, {Raw} raw, {Upserted} upserted, {Deactivated} deactivated",
            run.Id, run.Status, run.BoardsSucceeded, run.BoardsAttempted, run.RawPostingsFetched,
            run.JobsUpserted, run.JobsDeactivated);

        return run;
    }

    // ---- Bronze ----------------------------------------------------------------

    private async Task<(List<FetchedJob> Fetched, HashSet<(JobSourceType, string)> Succeeded)>
        FetchAndStoreBronzeAsync(IngestionRun run, List<string> errors, CancellationToken ct)
    {
        var boards = catalog.Load();
        run.BoardsAttempted = boards.Count;

        var allFetched = new List<FetchedJob>();
        var succeeded = new HashSet<(JobSourceType, string)>();
        var delayMs = Math.Max(0, options.Value.DelayBetweenBoardsMs);
        var first = true;

        foreach (var board in boards)
        {
            if (!registry.TryGet(board.Source, out var source))
            {
                errors.Add($"{board.Source}/{board.Token}: no connector registered");
                continue;
            }

            // Polite delay between board calls to avoid hammering a source.
            if (!first && delayMs > 0)
                await Task.Delay(delayMs, ct);
            first = false;

            try
            {
                var jobs = await source.FetchAsync(board.Token, ct);
                foreach (var job in jobs)
                {
                    db.RawJobPostings.Add(new RawJobPosting
                    {
                        Source = job.Source,
                        BoardToken = job.BoardToken,
                        SourceJobId = job.SourceJobId,
                        RawJson = job.RawJson,
                        FetchedAt = run.StartedAt,
                        IngestionRunId = run.Id
                    });
                }

                allFetched.AddRange(jobs);
                succeeded.Add((board.Source, board.Token));
                logger.LogDebug("Fetched {Count} from {Source}/{Token}", jobs.Count, board.Source, board.Token);
            }
            catch (Exception ex) when (ex is not OperationCanceledException)
            {
                errors.Add($"{board.Source}/{board.Token}: {ex.Message}");
                logger.LogWarning(ex, "Board {Source}/{Token} failed; isolating and continuing",
                    board.Source, board.Token);
            }
        }

        await db.SaveChangesAsync(ct);
        return (allFetched, succeeded);
    }

    // ---- Silver ----------------------------------------------------------------

    private async Task<(List<long> UpsertedJobIds, int Deactivated)> NormalizeToSilverAsync(
        List<FetchedJob> fetched,
        HashSet<(JobSourceType, string)> succeededBoards,
        DateTimeOffset now,
        CancellationToken ct)
    {
        var existing = await db.Jobs.ToListAsync(ct);
        var bySourceId = existing.ToDictionary(j => (j.Source, j.SourceJobId));

        // Owner of each dedup hash among currently active jobs (for cross-source dedup).
        var activeHashOwner = new Dictionary<string, (JobSourceType Source, string SourceJobId)>();
        foreach (var j in existing.Where(j => j.IsActive))
            activeHashOwner.TryAdd(j.DedupHash, (j.Source, j.SourceJobId));

        var seenKeys = new HashSet<(JobSourceType, string)>();

        foreach (var f in fetched)
        {
            var key = (f.Source, f.SourceJobId);
            if (!seenKeys.Add(key))
                continue; // same posting appeared twice in this run

            var hash = DedupHasher.Compute(f.Company, f.Title, f.Location);

            if (bySourceId.TryGetValue(key, out var job))
            {
                ApplyFields(job, f, hash, now, isNew: false);
                activeHashOwner[hash] = key;
            }
            else
            {
                // Cross-source dedup: skip a brand-new posting that duplicates an active job
                // already owned by a different source.
                if (activeHashOwner.TryGetValue(hash, out var owner) && owner.Source != f.Source)
                {
                    logger.LogDebug("Skipping cross-source duplicate {Source}/{Id} (hash owned by {Owner})",
                        f.Source, f.SourceJobId, owner.Source);
                    continue;
                }

                job = new Job { Source = f.Source, SourceJobId = f.SourceJobId, FirstSeenAt = now };
                ApplyFields(job, f, hash, now, isNew: true);
                db.Jobs.Add(job);
                activeHashOwner[hash] = key;
            }
        }

        // Deactivate postings that vanished from boards we successfully fetched.
        var deactivated = 0;
        foreach (var j in existing.Where(j => j.IsActive))
        {
            if (!succeededBoards.Contains((j.Source, j.BoardToken)))
                continue; // board failed or not in catalog — leave untouched
            if (!seenKeys.Contains((j.Source, j.SourceJobId)))
            {
                j.IsActive = false;
                deactivated++;
            }
        }

        await db.SaveChangesAsync(ct);

        // Jobs touched this run (new or refreshed) share this run's timestamp; collect their ids
        // now that inserts have been assigned keys.
        var ids = await db.Jobs
            .Where(j => j.LastSeenAt == now)
            .Select(j => j.Id)
            .ToListAsync(ct);

        return (ids, deactivated);
    }

    private static void ApplyFields(Job job, FetchedJob f, string hash, DateTimeOffset now, bool isNew)
    {
        job.BoardToken = f.BoardToken;
        job.Company = f.Company;
        job.Title = f.Title;
        job.Location = f.Location;
        job.Remote = f.Remote;
        job.Description = f.Description;
        job.ApplyUrl = f.ApplyUrl;
        // Npgsql 'timestamp with time zone' only accepts UTC-offset values.
        job.PostedAt = f.PostedAt?.ToUniversalTime();
        job.DedupHash = hash;
        job.LastSeenAt = now;
        job.IsActive = true;
    }

    // ---- Gold ------------------------------------------------------------------

    private async Task ExtractAndAggregateAsync(List<long> upsertedJobIds, DateTimeOffset now, CancellationToken ct)
    {
        // Re-extract skills for the jobs touched this run.
        if (upsertedJobIds.Count > 0)
        {
            var matcher = await skillExtractor.BuildMatcherAsync(ct);

            var jobs = await db.Jobs
                .Where(j => upsertedJobIds.Contains(j.Id))
                .ToListAsync(ct);

            var existingLinks = await db.JobSkills
                .Where(js => upsertedJobIds.Contains(js.JobId))
                .ToListAsync(ct);
            db.JobSkills.RemoveRange(existingLinks);

            foreach (var job in jobs)
                db.JobSkills.AddRange(ExtractLinks(matcher, job.Id, job.Title, job.Description));

            await db.SaveChangesAsync(ct);
        }

        await AggregateSkillDemandAsync(now, ct);
    }

    /// <summary>
    /// Re-runs skill extraction over every stored job's title+description (no re-fetch), rebuilds
    /// all <c>job_skills</c> links, then re-aggregates demand. Use to backfill existing rows after
    /// the skill dictionary or matcher logic changes, without hitting the live ATS boards.
    /// </summary>
    public async Task<int> ReextractAllAsync(CancellationToken ct = default)
    {
        var matcher = await skillExtractor.BuildMatcherAsync(ct);

        var jobs = await db.Jobs
            .Select(j => new { j.Id, j.Title, j.Description })
            .ToListAsync(ct);

        // Wipe every link in one statement, then rebuild from the current matcher.
        await db.JobSkills.ExecuteDeleteAsync(ct);

        foreach (var job in jobs)
            db.JobSkills.AddRange(ExtractLinks(matcher, job.Id, job.Title, job.Description));

        await db.SaveChangesAsync(ct);
        await AggregateSkillDemandAsync(clock.GetUtcNow(), ct);

        logger.LogInformation("Re-extracted skills for {Count} jobs", jobs.Count);
        return jobs.Count;
    }

    /// <summary>Skill links for one job from its title+description, shared by both extraction paths.</summary>
    private IEnumerable<JobSkill> ExtractLinks(SkillMatcher matcher, long jobId, string title, string description)
    {
        var text = $"{title}\n{description}";
        return matcher.Match(text).Select(skillId => new JobSkill { JobId = jobId, SkillId = skillId });
    }

    private async Task AggregateSkillDemandAsync(DateTimeOffset now, CancellationToken ct)
    {
        var today = DateOnly.FromDateTime(now.UtcDateTime);

        var roles = await db.Roles.ToListAsync(ct);

        // Active jobs with their extracted skills, deduplicated cross-source by content hash.
        var activeJobs = await db.Jobs
            .Where(j => j.IsActive)
            .Select(j => new
            {
                j.Id,
                j.Title,
                j.DedupHash,
                SkillIds = j.JobSkills.Select(js => js.SkillId).ToList()
            })
            .ToListAsync(ct);

        var distinctJobs = activeJobs
            .GroupBy(j => j.DedupHash)
            .Select(g => g.First())
            .ToList();

        // Replace today's snapshot.
        var existingToday = await db.SkillDemands
            .Where(d => d.SnapshotDate == today)
            .ToListAsync(ct);
        db.SkillDemands.RemoveRange(existingToday);

        foreach (var role in roles)
        {
            var patterns = role.TitlePatterns;
            var matching = distinctJobs
                .Where(j => patterns.Any(p => j.Title.Contains(p, StringComparison.OrdinalIgnoreCase)))
                .ToList();

            var counts = matching
                .SelectMany(j => j.SkillIds.Distinct())
                .GroupBy(id => id)
                .Select(g => new { SkillId = g.Key, Count = g.Count() });

            foreach (var c in counts)
            {
                db.SkillDemands.Add(new SkillDemand
                {
                    RoleId = role.Id,
                    SkillId = c.SkillId,
                    JobCount = c.Count,
                    SnapshotDate = today
                });
            }
        }

        await db.SaveChangesAsync(ct);
    }
}
