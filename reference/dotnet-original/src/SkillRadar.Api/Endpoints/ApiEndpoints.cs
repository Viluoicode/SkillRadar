using Hangfire;
using Microsoft.EntityFrameworkCore;
using SkillRadar.Api.Contracts;
using SkillRadar.Core.Entities;
using SkillRadar.Data;
using SkillRadar.Ingestion;

namespace SkillRadar.Api.Endpoints;

public static class ApiEndpoints
{
    public static void MapSkillRadarApi(this IEndpointRouteBuilder app)
    {
        var api = app.MapGroup("/api");

        api.MapGet("/roles", GetRoles);
        api.MapGet("/skill-demand", GetSkillDemand);
        api.MapGet("/jobs", GetJobs);
        api.MapGet("/stats", GetStats);
        api.MapPost("/ingest", TriggerIngest);
        api.MapPost("/reextract", TriggerReextract);
    }

    private static async Task<IResult> GetRoles(SkillRadarDbContext db, CancellationToken ct)
    {
        var roles = await db.Roles
            .OrderBy(r => r.Name)
            .Select(r => new RoleDto(r.Id, r.Name))
            .ToListAsync(ct);
        return Results.Ok(roles);
    }

    private static async Task<IResult> GetSkillDemand(
        SkillRadarDbContext db, int role, int top, CancellationToken ct)
    {
        if (top <= 0) top = 20;

        // Use the most recent snapshot available for this role.
        var latest = await db.SkillDemands
            .Where(d => d.RoleId == role)
            .MaxAsync(d => (DateOnly?)d.SnapshotDate, ct);

        if (latest is null)
            return Results.Ok(Array.Empty<SkillDemandDto>());

        var demand = await db.SkillDemands
            .Where(d => d.RoleId == role && d.SnapshotDate == latest)
            .OrderByDescending(d => d.JobCount)
            .ThenBy(d => d.Skill.Name)
            .Take(top)
            .Select(d => new SkillDemandDto(d.SkillId, d.Skill.Name, d.Skill.Category, d.JobCount))
            .ToListAsync(ct);

        return Results.Ok(demand);
    }

    private static async Task<IResult> GetJobs(
        SkillRadarDbContext db,
        string? skill,
        string? source,
        string? company,
        string? location,
        bool? remote,
        DateTimeOffset? postedAfter,
        string? search,
        int page,
        int pageSize,
        CancellationToken ct)
    {
        if (page <= 0) page = 1;
        if (pageSize is <= 0 or > 100) pageSize = 25;

        var query = db.Jobs.Where(j => j.IsActive);

        if (!string.IsNullOrWhiteSpace(skill))
            query = query.Where(j => j.JobSkills.Any(js => js.Skill.Name == skill));

        if (!string.IsNullOrWhiteSpace(source) && Enum.TryParse<JobSourceType>(source, true, out var src))
            query = query.Where(j => j.Source == src);

        if (!string.IsNullOrWhiteSpace(company))
            query = query.Where(j => EF.Functions.ILike(j.Company, $"%{company}%"));

        if (!string.IsNullOrWhiteSpace(location))
            query = query.Where(j => j.Location != null && EF.Functions.ILike(j.Location, $"%{location}%"));

        if (remote is not null)
            query = query.Where(j => j.Remote == remote);

        if (postedAfter is not null)
            query = query.Where(j => j.PostedAt >= postedAfter);

        if (!string.IsNullOrWhiteSpace(search))
            query = query.Where(j => EF.Functions.ILike(j.Title, $"%{search}%"));

        var total = await query.CountAsync(ct);

        var items = await query
            .OrderByDescending(j => j.PostedAt ?? j.FirstSeenAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .Select(j => new JobDto(
                j.Id,
                j.Company,
                j.Title,
                j.Location,
                j.Remote,
                j.Source.ToString(),
                j.ApplyUrl,
                j.PostedAt,
                j.JobSkills.Select(js => js.Skill.Name).OrderBy(n => n).ToList()))
            .ToListAsync(ct);

        return Results.Ok(new JobListDto(total, page, pageSize, items));
    }

    private static async Task<IResult> GetStats(SkillRadarDbContext db, CancellationToken ct)
    {
        var lastRun = await db.IngestionRuns
            .OrderByDescending(r => r.StartedAt)
            .Select(r => new { r.StartedAt, r.Status })
            .FirstOrDefaultAsync(ct);

        var stats = new StatsDto(
            ActiveJobs: await db.Jobs.CountAsync(j => j.IsActive, ct),
            TotalSkills: await db.Skills.CountAsync(ct),
            Roles: await db.Roles.CountAsync(ct),
            LastRunAt: lastRun?.StartedAt,
            LastRunStatus: lastRun?.Status.ToString());

        return Results.Ok(stats);
    }

    private static IResult TriggerIngest(IBackgroundJobClient jobs)
    {
        var jobId = jobs.Enqueue<IngestionJob>(j => j.RunAsync("OnDemand", CancellationToken.None));
        return Results.Accepted($"/hangfire/jobs/details/{jobId}", new IngestTriggeredDto(jobId));
    }

    // Backfill: re-extract skills for all stored jobs (no re-fetch). Run after dictionary/matcher changes.
    private static IResult TriggerReextract(IBackgroundJobClient jobs)
    {
        var jobId = jobs.Enqueue<IngestionJob>(j => j.ReextractAllAsync(CancellationToken.None));
        return Results.Accepted($"/hangfire/jobs/details/{jobId}", new IngestTriggeredDto(jobId));
    }
}
