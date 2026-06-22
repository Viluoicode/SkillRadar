namespace SkillRadar.Core.Entities;

public enum IngestionRunStatus
{
    Running = 0,
    Succeeded = 1,
    CompletedWithErrors = 2,
    Failed = 3
}

/// <summary>
/// Observability record for a single pipeline execution: when it ran, how many postings
/// were fetched/normalized, and any per-source errors encountered.
/// </summary>
public class IngestionRun
{
    public long Id { get; set; }

    public DateTimeOffset StartedAt { get; set; }
    public DateTimeOffset? FinishedAt { get; set; }
    public IngestionRunStatus Status { get; set; } = IngestionRunStatus.Running;

    public int BoardsAttempted { get; set; }
    public int BoardsSucceeded { get; set; }
    public int RawPostingsFetched { get; set; }
    public int JobsUpserted { get; set; }
    public int JobsDeactivated { get; set; }

    /// <summary>How the run was triggered: "Scheduled" or "OnDemand".</summary>
    public string Trigger { get; set; } = string.Empty;

    /// <summary>Newline-delimited per-source error messages (null when none).</summary>
    public string? Errors { get; set; }
}
