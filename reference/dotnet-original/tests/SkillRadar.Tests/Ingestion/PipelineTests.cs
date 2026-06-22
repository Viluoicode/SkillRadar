using Microsoft.EntityFrameworkCore;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using static SkillRadar.Tests.Ingestion.PipelineHarness;

namespace SkillRadar.Tests.Ingestion;

public class PipelineTests
{
    [Fact]
    public async Task Fetch_writes_bronze_and_silver_and_logs_run()
    {
        using var h = new PipelineHarness();
        var gh = new FakeJobSource(JobSourceType.Greenhouse)
            .Returns("acme", Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"));
        var pipeline = h.Build(
            new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } }, gh);

        var run = await pipeline.RunAsync("Test");

        Assert.Equal(IngestionRunStatus.Succeeded, run.Status);
        Assert.Equal(1, run.RawPostingsFetched);
        Assert.Equal(1, run.JobsUpserted);
        Assert.Equal(1, await h.Db.RawJobPostings.CountAsync());
        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => j.IsActive));
    }

    [Fact]
    public async Task Rerunning_does_not_duplicate_and_refreshes_last_seen()
    {
        using var h = new PipelineHarness();
        var gh = new FakeJobSource(JobSourceType.Greenhouse)
            .Returns("acme", Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"));
        var boards = new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } };

        await h.Build(boards, gh).RunAsync("Run1");
        var firstSeen = (await h.Db.Jobs.SingleAsync()).LastSeenAt;

        await h.Build(boards, gh).RunAsync("Run2");

        var jobs = await h.Db.Jobs.ToListAsync();
        Assert.Single(jobs); // no duplicate
        Assert.True(jobs[0].LastSeenAt >= firstSeen);
    }

    [Fact]
    public async Task Same_posting_twice_in_one_run_is_deduped()
    {
        using var h = new PipelineHarness();
        var gh = new FakeJobSource(JobSourceType.Greenhouse)
            .Returns("acme",
                Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"),
                Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"));
        var pipeline = h.Build(
            new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } }, gh);

        await pipeline.RunAsync("Test");

        Assert.Equal(1, await h.Db.Jobs.CountAsync());
    }

    [Fact]
    public async Task Cross_source_duplicate_is_skipped()
    {
        using var h = new PipelineHarness();
        // Same company/title/location offered on both Lever and Ashby (e.g. Ramp).
        var lever = new FakeJobSource(JobSourceType.Lever)
            .Returns("ramp", Job(JobSourceType.Lever, "ramp", "L1", "Software Engineer", "Ramp", "Remote"));
        var ashby = new FakeJobSource(JobSourceType.Ashby)
            .Returns("ramp", Job(JobSourceType.Ashby, "ramp", "A1", "Software Engineer", "Ramp", "Remote"));

        var pipeline = h.Build(new[]
        {
            new BoardConfig { Source = JobSourceType.Lever, Token = "ramp" },
            new BoardConfig { Source = JobSourceType.Ashby, Token = "ramp" }
        }, lever, ashby);

        await pipeline.RunAsync("Test");

        // Both raw payloads captured (Bronze), but only one canonical job (Silver).
        Assert.Equal(2, await h.Db.RawJobPostings.CountAsync());
        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => j.IsActive));
    }

    [Fact]
    public async Task Vanished_posting_is_deactivated()
    {
        using var h = new PipelineHarness();
        var boards = new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } };

        var withTwo = new FakeJobSource(JobSourceType.Greenhouse).Returns("acme",
            Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"),
            Job(JobSourceType.Greenhouse, "acme", "2", "Frontend Engineer"));
        await h.Build(boards, withTwo).RunAsync("Run1");
        Assert.Equal(2, await h.Db.Jobs.CountAsync(j => j.IsActive));

        // Second run: job "2" disappeared from the feed.
        var withOne = new FakeJobSource(JobSourceType.Greenhouse).Returns("acme",
            Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"));
        await h.Build(boards, withOne).RunAsync("Run2");

        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => j.IsActive));
        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => !j.IsActive));
    }

    [Fact]
    public async Task Failing_board_is_isolated_and_others_still_ingest()
    {
        using var h = new PipelineHarness();
        var gh = new FakeJobSource(JobSourceType.Greenhouse)
            .Fails("broken")
            .Returns("good", Job(JobSourceType.Greenhouse, "good", "1", "Backend Engineer"));

        var pipeline = h.Build(new[]
        {
            new BoardConfig { Source = JobSourceType.Greenhouse, Token = "broken" },
            new BoardConfig { Source = JobSourceType.Greenhouse, Token = "good" }
        }, gh);

        var run = await pipeline.RunAsync("Test");

        Assert.Equal(IngestionRunStatus.CompletedWithErrors, run.Status);
        Assert.Equal(2, run.BoardsAttempted);
        Assert.Equal(1, run.BoardsSucceeded);
        Assert.NotNull(run.Errors);
        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => j.IsActive));
    }

    [Fact]
    public async Task Failing_board_does_not_deactivate_its_existing_jobs()
    {
        using var h = new PipelineHarness();
        var boards = new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } };

        var ok = new FakeJobSource(JobSourceType.Greenhouse)
            .Returns("acme", Job(JobSourceType.Greenhouse, "acme", "1", "Backend Engineer"));
        await h.Build(boards, ok).RunAsync("Run1");

        // The board fails on the next run; its previously-ingested job must stay active.
        var broken = new FakeJobSource(JobSourceType.Greenhouse).Fails("acme");
        await h.Build(boards, broken).RunAsync("Run2");

        Assert.Equal(1, await h.Db.Jobs.CountAsync(j => j.IsActive));
    }
}
