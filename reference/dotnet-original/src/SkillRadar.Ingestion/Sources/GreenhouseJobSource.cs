using System.Text.Json;
using Microsoft.Extensions.Logging;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using SkillRadar.Core.Text;
using SkillRadar.Ingestion.Json;

namespace SkillRadar.Ingestion.Sources;

/// <summary>
/// Connector for Greenhouse public job boards.
/// Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
/// </summary>
public class GreenhouseJobSource(HttpClient http, ILogger<GreenhouseJobSource> logger) : IJobSource
{
    public JobSourceType Source => JobSourceType.Greenhouse;

    public async Task<IReadOnlyList<FetchedJob>> FetchAsync(string boardToken, CancellationToken cancellationToken = default)
    {
        var url = $"v1/boards/{Uri.EscapeDataString(boardToken)}/jobs?content=true";
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

            string? location = null;
            if (job.TryGetChild("location", out var loc))
                location = loc.GetString("name");

            var company = job.GetString("company_name");
            var description = TextNormalizer.StripHtml(job.GetString("content"));

            results.Add(new FetchedJob
            {
                Source = Source,
                BoardToken = boardToken,
                SourceJobId = id,
                RawJson = job.GetRawText(),
                Company = string.IsNullOrWhiteSpace(company) ? boardToken : company,
                Title = job.GetString("title") ?? string.Empty,
                Location = location,
                Remote = LooksRemote(location),
                Description = description,
                ApplyUrl = job.GetString("absolute_url") ?? string.Empty,
                PostedAt = ParseDate(job.GetString("updated_at") ?? job.GetString("first_published"))
            });
        }

        logger.LogDebug("Greenhouse board {Token} returned {Count} postings", boardToken, results.Count);
        return results;
    }

    private static bool LooksRemote(string? location) =>
        location is not null && location.Contains("remote", StringComparison.OrdinalIgnoreCase);

    private static DateTimeOffset? ParseDate(string? value) =>
        DateTimeOffset.TryParse(value, out var dt) ? dt : null;
}
