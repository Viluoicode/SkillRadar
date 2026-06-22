using SkillRadar.Core.Entities;

namespace SkillRadar.Core.Ingestion;

/// <summary>One curated company board to ingest (from data/sources.json).</summary>
public record BoardConfig
{
    public required JobSourceType Source { get; init; }

    /// <summary>The board token / company slug in the ATS URL.</summary>
    public required string Token { get; init; }

    /// <summary>
    /// Optional display company name. Used as a fallback when the feed does not carry one
    /// (e.g. some Greenhouse boards).
    /// </summary>
    public string? Company { get; init; }
}

/// <summary>Root of data/sources.json.</summary>
public record SourceCatalog
{
    public List<BoardConfig> Boards { get; init; } = new();
}
