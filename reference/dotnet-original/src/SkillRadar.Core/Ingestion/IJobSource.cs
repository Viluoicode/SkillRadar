using SkillRadar.Core.Entities;

namespace SkillRadar.Core.Ingestion;

/// <summary>
/// A connector to one ATS platform. Implementations fetch all live postings for a single
/// board token and return them in a canonical shape. Implementations should be resilient
/// (retry/backoff handled by the injected <see cref="HttpClient"/>) and must surface
/// transport failures as exceptions so the pipeline can isolate a failing board.
/// </summary>
public interface IJobSource
{
    JobSourceType Source { get; }

    /// <summary>Fetches all current postings for the given board token / company slug.</summary>
    Task<IReadOnlyList<FetchedJob>> FetchAsync(string boardToken, CancellationToken cancellationToken = default);
}
