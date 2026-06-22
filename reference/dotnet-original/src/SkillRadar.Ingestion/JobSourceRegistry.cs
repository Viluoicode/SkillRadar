using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;

namespace SkillRadar.Ingestion;

/// <summary>Resolves the registered <see cref="IJobSource"/> connector for a source type.</summary>
public class JobSourceRegistry
{
    private readonly Dictionary<JobSourceType, IJobSource> _sources;

    public JobSourceRegistry(IEnumerable<IJobSource> sources)
    {
        _sources = sources.ToDictionary(s => s.Source);
    }

    public bool TryGet(JobSourceType type, out IJobSource source) =>
        _sources.TryGetValue(type, out source!);
}
