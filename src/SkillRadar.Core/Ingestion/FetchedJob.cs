using SkillRadar.Core.Entities;

namespace SkillRadar.Core.Ingestion;

/// <summary>
/// A single posting returned by an <see cref="IJobSource"/> connector: the verbatim raw
/// payload (for the Bronze layer) plus the fields parsed into a canonical shape (for Silver).
/// </summary>
public record FetchedJob
{
    public required JobSourceType Source { get; init; }
    public required string BoardToken { get; init; }
    public required string SourceJobId { get; init; }

    /// <summary>The verbatim JSON for this single posting, stored as-is in Bronze.</summary>
    public required string RawJson { get; init; }

    public required string Company { get; init; }
    public required string Title { get; init; }
    public string? Location { get; init; }
    public bool Remote { get; init; }
    public string Description { get; init; } = string.Empty;
    public string ApplyUrl { get; init; } = string.Empty;
    public DateTimeOffset? PostedAt { get; init; }
}
