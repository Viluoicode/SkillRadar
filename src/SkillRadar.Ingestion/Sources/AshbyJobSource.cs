using System.Text.Json;
using Microsoft.Extensions.Logging;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using SkillRadar.Core.Text;
using SkillRadar.Ingestion.Json;

namespace SkillRadar.Ingestion.Sources;

/// <summary>
/// Connector for Ashby public job boards.
/// Endpoint: GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true
/// </summary>
public class AshbyJobSource(HttpClient http, ILogger<AshbyJobSource> logger) : IJobSource
{
    public JobSourceType Source => JobSourceType.Ashby;

    public async Task<IReadOnlyList<FetchedJob>> FetchAsync(string boardToken, CancellationToken cancellationToken = default)
    {
        var url = $"posting-api/job-board/{Uri.EscapeDataString(boardToken)}?includeCompensation=true";
        using var response = await http.GetAsync(url, cancellationToken);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var doc = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);

        var results = new List<FetchedJob>();
        if (!doc.RootElement.TryGetChild("jobs", out var jobs) || jobs.ValueKind != JsonValueKind.Array)
            return results;

        foreach (var job in jobs.EnumerateArray())
        {
            var id = job.GetId("id");
            if (string.IsNullOrEmpty(id))
                continue;

            var description = job.GetString("descriptionPlain");
            if (string.IsNullOrWhiteSpace(description))
                description = TextNormalizer.StripHtml(job.GetString("descriptionHtml"));

            results.Add(new FetchedJob
            {
                Source = Source,
                BoardToken = boardToken,
                SourceJobId = id,
                RawJson = job.GetRawText(),
                Company = boardToken,
                Title = job.GetString("title") ?? string.Empty,
                Location = job.GetString("location"),
                Remote = job.GetBool("isRemote"),
                Description = description ?? string.Empty,
                ApplyUrl = job.GetString("jobUrl") ?? job.GetString("applyUrl") ?? string.Empty,
                PostedAt = ParseDate(job.GetString("publishedAt"))
            });
        }

        logger.LogDebug("Ashby board {Token} returned {Count} postings", boardToken, results.Count);
        return results;
    }

    private static DateTimeOffset? ParseDate(string? value) =>
        DateTimeOffset.TryParse(value, out var dt) ? dt : null;
}
