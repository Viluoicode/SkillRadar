using System.Text.Json;
using Microsoft.Extensions.Logging;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using SkillRadar.Core.Text;
using SkillRadar.Ingestion.Json;

namespace SkillRadar.Ingestion.Sources;

/// <summary>
/// Connector for Lever public postings.
/// Endpoint: GET https://api.lever.co/v0/postings/{token}?mode=json
/// </summary>
public class LeverJobSource(HttpClient http, ILogger<LeverJobSource> logger) : IJobSource
{
    public JobSourceType Source => JobSourceType.Lever;

    public async Task<IReadOnlyList<FetchedJob>> FetchAsync(string boardToken, CancellationToken cancellationToken = default)
    {
        var url = $"v0/postings/{Uri.EscapeDataString(boardToken)}?mode=json";
        using var response = await http.GetAsync(url, cancellationToken);
        response.EnsureSuccessStatusCode();

        await using var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
        using var doc = await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken);

        var results = new List<FetchedJob>();
        if (doc.RootElement.ValueKind != JsonValueKind.Array)
            return results;

        foreach (var job in doc.RootElement.EnumerateArray())
        {
            var id = job.GetId("id");
            if (string.IsNullOrEmpty(id))
                continue;

            string? location = null;
            string? commitment = null;
            if (job.TryGetChild("categories", out var cats))
            {
                location = cats.GetString("location");
                commitment = cats.GetString("commitment");
            }

            // Prefer plain text; fall back to stripping the HTML description.
            var description = job.GetString("descriptionPlain");
            if (string.IsNullOrWhiteSpace(description))
                description = TextNormalizer.StripHtml(job.GetString("description"));

            var workplace = job.GetString("workplaceType");

            results.Add(new FetchedJob
            {
                Source = Source,
                BoardToken = boardToken,
                SourceJobId = id,
                RawJson = job.GetRawText(),
                Company = boardToken,
                Title = job.GetString("text") ?? string.Empty,
                Location = location,
                Remote = string.Equals(workplace, "remote", StringComparison.OrdinalIgnoreCase)
                         || LooksRemote(location) || LooksRemote(commitment),
                Description = description ?? string.Empty,
                ApplyUrl = job.GetString("hostedUrl") ?? job.GetString("applyUrl") ?? string.Empty,
                PostedAt = ParseEpochMs(job)
            });
        }

        logger.LogDebug("Lever board {Token} returned {Count} postings", boardToken, results.Count);
        return results;
    }

    private static bool LooksRemote(string? value) =>
        value is not null && value.Contains("remote", StringComparison.OrdinalIgnoreCase);

    private static DateTimeOffset? ParseEpochMs(JsonElement job)
    {
        if (job.TryGetProperty("createdAt", out var v) && v.ValueKind == JsonValueKind.Number &&
            v.TryGetInt64(out var ms))
        {
            return DateTimeOffset.FromUnixTimeMilliseconds(ms);
        }
        return null;
    }
}
