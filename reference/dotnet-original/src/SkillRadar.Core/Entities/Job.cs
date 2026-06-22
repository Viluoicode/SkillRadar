namespace SkillRadar.Core.Entities;

/// <summary>
/// Silver layer: a normalized, deduplicated job posting. Upserted on each ingestion run;
/// <see cref="LastSeenAt"/> is refreshed when the posting still appears in its feed and
/// <see cref="IsActive"/> is cleared once it disappears.
/// </summary>
public class Job
{
    public long Id { get; set; }

    public JobSourceType Source { get; set; }

    /// <summary>The posting's native id within its source.</summary>
    public string SourceJobId { get; set; } = string.Empty;

    /// <summary>The board token this posting was ingested from (scopes deactivation/debugging).</summary>
    public string BoardToken { get; set; } = string.Empty;

    public string Company { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string? Location { get; set; }
    public bool Remote { get; set; }

    /// <summary>Plain-text job description (HTML stripped) used for skill extraction.</summary>
    public string Description { get; set; } = string.Empty;

    /// <summary>Outbound link to apply at the original source.</summary>
    public string ApplyUrl { get; set; } = string.Empty;

    public DateTimeOffset? PostedAt { get; set; }

    /// <summary>
    /// Normalized hash of (company + title + location) used to catch the same role
    /// cross-posted on multiple boards/sources.
    /// </summary>
    public string DedupHash { get; set; } = string.Empty;

    public DateTimeOffset FirstSeenAt { get; set; }
    public DateTimeOffset LastSeenAt { get; set; }
    public bool IsActive { get; set; } = true;

    public ICollection<JobSkill> JobSkills { get; set; } = new List<JobSkill>();
}
