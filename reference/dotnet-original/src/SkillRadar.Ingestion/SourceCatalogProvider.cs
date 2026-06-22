using System.Text.Json;
using Microsoft.Extensions.Options;
using SkillRadar.Core.Ingestion;

namespace SkillRadar.Ingestion;

/// <summary>Loads the curated board list from data/sources.json.</summary>
public class SourceCatalogProvider(IOptions<IngestionOptions> options)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web)
    {
        Converters = { new System.Text.Json.Serialization.JsonStringEnumConverter() }
    };

    public IReadOnlyList<BoardConfig> Load()
    {
        var path = options.Value.SourcesPath;
        if (!File.Exists(path))
            throw new FileNotFoundException($"Sources catalog not found: {path}");

        using var stream = File.OpenRead(path);
        var catalog = JsonSerializer.Deserialize<SourceCatalog>(stream, JsonOptions);
        return catalog?.Boards ?? new List<BoardConfig>();
    }
}
