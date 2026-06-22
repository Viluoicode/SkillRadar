namespace SkillRadar.Core.Entities;

/// <summary>
/// Bronze layer: an immutable, append-only raw payload for a single posting as fetched
/// from an ATS feed. Stored verbatim so the pipeline can be replayed/debugged independently
/// of upstream schema changes.
/// </summary>
public class RawJobPosting
{
    public long Id { get; set; }

    public JobSourceType Source { get; set; }

    /// <summary>The board token / company slug this posting was fetched from.</summary>
    public string BoardToken { get; set; } = string.Empty;

    /// <summary>The posting's native id within its source (used as the primary dedup key).</summary>
    public string SourceJobId { get; set; } = string.Empty;

    /// <summary>The raw JSON payload for this single posting (jsonb column).</summary>
    public string RawJson { get; set; } = string.Empty;

    public DateTimeOffset FetchedAt { get; set; }

    /// <summary>The ingestion run that produced this row.</summary>
    public long IngestionRunId { get; set; }
}
