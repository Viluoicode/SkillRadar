using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using SkillRadar.Data;
using SkillRadar.Ingestion;

namespace SkillRadar.Tests.Ingestion;

/// <summary>Wires an <see cref="IngestionPipeline"/> over an in-memory database for tests.</summary>
public sealed class PipelineHarness : IDisposable
{
    public SkillRadarDbContext Db { get; }
    private readonly string _sourcesPath;

    public PipelineHarness()
    {
        var options = new DbContextOptionsBuilder<SkillRadarDbContext>()
            .UseInMemoryDatabase($"skillradar-{Guid.NewGuid()}")
            .Options;
        Db = new SkillRadarDbContext(options);
        _sourcesPath = Path.Combine(Path.GetTempPath(), $"sources-{Guid.NewGuid()}.json");
    }

    public IngestionPipeline Build(IEnumerable<BoardConfig> boards, params IJobSource[] sources)
    {
        File.WriteAllText(_sourcesPath, System.Text.Json.JsonSerializer.Serialize(
            new SourceCatalog { Boards = boards.ToList() },
            new System.Text.Json.JsonSerializerOptions
            {
                Converters = { new System.Text.Json.Serialization.JsonStringEnumConverter() }
            }));

        var opts = Options.Create(new IngestionOptions
        {
            SourcesPath = _sourcesPath,
            DelayBetweenBoardsMs = 0
        });

        var catalog = new SourceCatalogProvider(opts);
        var registry = new JobSourceRegistry(sources);
        var extractor = new SkillExtractor(Db);

        return new IngestionPipeline(Db, catalog, registry, extractor, TimeProvider.System, opts,
            NullLogger<IngestionPipeline>.Instance);
    }

    public static FetchedJob Job(JobSourceType source, string token, string id, string title,
        string company = "Acme", string? location = "Remote", string description = "") => new()
    {
        Source = source,
        BoardToken = token,
        SourceJobId = id,
        RawJson = "{}",
        Company = company,
        Title = title,
        Location = location,
        Description = description,
        ApplyUrl = $"https://example.com/{id}"
    };

    public void Dispose()
    {
        Db.Dispose();
        if (File.Exists(_sourcesPath))
            File.Delete(_sourcesPath);
    }
}
