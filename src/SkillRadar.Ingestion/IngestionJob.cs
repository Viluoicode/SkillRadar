namespace SkillRadar.Ingestion;

/// <summary>
/// Stable entry point invoked by Hangfire (recurring + on-demand). Kept dependency-free of
/// Hangfire itself so it can also be called directly (e.g. from tests or a CLI).
/// </summary>
public class IngestionJob(IngestionPipeline pipeline)
{
    public Task RunAsync(string trigger, CancellationToken ct = default) =>
        pipeline.RunAsync(trigger, ct);

    /// <summary>Backfill entry point: re-extract skills for all stored jobs (no re-fetch).</summary>
    public Task<int> ReextractAllAsync(CancellationToken ct = default) =>
        pipeline.ReextractAllAsync(ct);
}
