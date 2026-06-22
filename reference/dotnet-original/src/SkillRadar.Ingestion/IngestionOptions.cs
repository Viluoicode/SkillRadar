namespace SkillRadar.Ingestion;

/// <summary>Configuration for the ingestion pipeline (bound from appsettings "Ingestion").</summary>
public class IngestionOptions
{
    /// <summary>Absolute or content-root-relative path to data/sources.json.</summary>
    public string SourcesPath { get; set; } = "data/sources.json";

    /// <summary>Absolute or content-root-relative path to data/skills.seed.json.</summary>
    public string SkillsSeedPath { get; set; } = "data/skills.seed.json";

    /// <summary>Polite delay between consecutive board fetches, in milliseconds.</summary>
    public int DelayBetweenBoardsMs { get; set; } = 500;

    /// <summary>Cron expression for the recurring Hangfire ingestion job.</summary>
    public string Cron { get; set; } = "0 * * * *"; // hourly
}
