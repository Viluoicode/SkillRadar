using Microsoft.EntityFrameworkCore;
using SkillRadar.Core.Entities;
using SkillRadar.Core.Ingestion;
using static SkillRadar.Tests.Ingestion.PipelineHarness;

namespace SkillRadar.Tests.Ingestion;

public class GoldAggregationTests
{
    private static void Seed(Data.SkillRadarDbContext db)
    {
        db.Skills.Add(new Skill { Id = 1, Name = "Python", Category = "Language" });
        db.Skills.Add(new Skill { Id = 2, Name = "Kubernetes", Category = "DevOps", Aliases = { new SkillAlias { Alias = "k8s" } } });
        db.Roles.Add(new Role { Id = 1, Name = "Data Engineer", TitlePatterns = new() { "data engineer" } });
        db.SaveChanges();
    }

    [Fact]
    public async Task Extracts_skills_and_aggregates_demand_for_matching_role()
    {
        using var h = new PipelineHarness();
        Seed(h.Db);

        var gh = new FakeJobSource(JobSourceType.Greenhouse).Returns("acme",
            Job(JobSourceType.Greenhouse, "acme", "1", "Senior Data Engineer", description: "We use Python and k8s daily."),
            Job(JobSourceType.Greenhouse, "acme", "2", "Data Engineer", description: "Strong Python required."),
            Job(JobSourceType.Greenhouse, "acme", "3", "Frontend Engineer", description: "Python optional."));

        var pipeline = h.Build(
            new[] { new BoardConfig { Source = JobSourceType.Greenhouse, Token = "acme" } }, gh);

        await pipeline.RunAsync("Test");

        // job_skills: job 1 -> Python + Kubernetes(via k8s), job 2 -> Python, job 3 -> Python
        Assert.Equal(4, await h.Db.JobSkills.CountAsync());

        // skill_demand for Data Engineer: Python in 2 matching jobs, Kubernetes in 1.
        var today = DateOnly.FromDateTime(DateTime.UtcNow);
        var pythonDemand = await h.Db.SkillDemands.SingleAsync(d => d.RoleId == 1 && d.SkillId == 1 && d.SnapshotDate == today);
        var k8sDemand = await h.Db.SkillDemands.SingleAsync(d => d.RoleId == 1 && d.SkillId == 2 && d.SnapshotDate == today);

        Assert.Equal(2, pythonDemand.JobCount); // jobs 1 and 2 (job 3 is Frontend)
        Assert.Equal(1, k8sDemand.JobCount);
    }
}
