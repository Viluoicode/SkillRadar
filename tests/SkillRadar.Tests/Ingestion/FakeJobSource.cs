using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;

namespace SkillRadar.Tests.Ingestion;

/// <summary>An <see cref="IJobSource"/> that returns scripted results per board token.</summary>
public class FakeJobSource(JobSourceType source) : IJobSource
{
    private readonly Dictionary<string, IReadOnlyList<FetchedJob>> _responses = new();
    private readonly HashSet<string> _failing = new();

    public JobSourceType Source { get; } = source;
    public int CallCount { get; private set; }

    public FakeJobSource Returns(string token, params FetchedJob[] jobs)
    {
        _responses[token] = jobs;
        return this;
    }

    public FakeJobSource Fails(string token)
    {
        _failing.Add(token);
        return this;
    }

    public Task<IReadOnlyList<FetchedJob>> FetchAsync(string boardToken, CancellationToken cancellationToken = default)
    {
        CallCount++;
        if (_failing.Contains(boardToken))
            throw new HttpRequestException($"simulated failure for {boardToken}");

        return Task.FromResult(_responses.TryGetValue(boardToken, out var jobs)
            ? jobs
            : Array.Empty<FetchedJob>());
    }
}
