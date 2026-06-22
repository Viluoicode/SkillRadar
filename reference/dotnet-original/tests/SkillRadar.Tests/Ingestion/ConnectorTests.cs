using System.Net;
using Microsoft.Extensions.Logging.Abstractions;
using SkillRadar.Core.Entities;
using SkillRadar.Ingestion.Sources;

namespace SkillRadar.Tests.Ingestion;

public class ConnectorTests
{
    [Fact]
    public async Task Greenhouse_parses_postings()
    {
        const string body = """
        {
          "jobs": [
            {
              "id": 12345,
              "title": "Senior Backend Engineer",
              "absolute_url": "https://boards.greenhouse.io/acme/jobs/12345",
              "updated_at": "2026-05-01T10:00:00-04:00",
              "location": { "name": "Remote - US" },
              "company_name": "Acme",
              "content": "&lt;p&gt;We use &lt;b&gt;Go&lt;/b&gt; and Kubernetes.&lt;/p&gt;"
            }
          ]
        }
        """;
        var client = StubHttpMessageHandler.Client(body, "https://boards-api.greenhouse.io/");
        var source = new GreenhouseJobSource(client, NullLogger<GreenhouseJobSource>.Instance);

        var jobs = await source.FetchAsync("acme");

        var job = Assert.Single(jobs);
        Assert.Equal(JobSourceType.Greenhouse, job.Source);
        Assert.Equal("12345", job.SourceJobId);
        Assert.Equal("Senior Backend Engineer", job.Title);
        Assert.Equal("Acme", job.Company);
        Assert.Equal("Remote - US", job.Location);
        Assert.True(job.Remote);
        Assert.Equal("https://boards.greenhouse.io/acme/jobs/12345", job.ApplyUrl);
        Assert.Contains("Go", job.Description);
        Assert.Contains("Kubernetes", job.Description);
        Assert.DoesNotContain("<p>", job.Description); // HTML stripped
        Assert.NotNull(job.PostedAt);
    }

    [Fact]
    public async Task Lever_parses_postings()
    {
        const string body = """
        [
          {
            "id": "abc-123",
            "text": "Data Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/abc-123",
            "categories": { "location": "New York", "commitment": "Full-time" },
            "descriptionPlain": "Build pipelines with Python and Spark.",
            "workplaceType": "onsite",
            "createdAt": 1714564800000
          }
        ]
        """;
        var client = StubHttpMessageHandler.Client(body, "https://api.lever.co/");
        var source = new LeverJobSource(client, NullLogger<LeverJobSource>.Instance);

        var jobs = await source.FetchAsync("acme");

        var job = Assert.Single(jobs);
        Assert.Equal(JobSourceType.Lever, job.Source);
        Assert.Equal("abc-123", job.SourceJobId);
        Assert.Equal("Data Engineer", job.Title);
        Assert.Equal("New York", job.Location);
        Assert.False(job.Remote);
        Assert.Contains("Python", job.Description);
        Assert.Equal(DateTimeOffset.FromUnixTimeMilliseconds(1714564800000), job.PostedAt);
    }

    [Fact]
    public async Task Ashby_parses_postings()
    {
        const string body = """
        {
          "jobs": [
            {
              "id": "f1e2",
              "title": "ML Engineer",
              "location": "San Francisco",
              "isRemote": true,
              "descriptionPlain": "Work with PyTorch and TensorFlow.",
              "jobUrl": "https://jobs.ashbyhq.com/acme/f1e2",
              "publishedAt": "2026-04-15T00:00:00Z"
            }
          ]
        }
        """;
        var client = StubHttpMessageHandler.Client(body, "https://api.ashbyhq.com/");
        var source = new AshbyJobSource(client, NullLogger<AshbyJobSource>.Instance);

        var jobs = await source.FetchAsync("acme");

        var job = Assert.Single(jobs);
        Assert.Equal(JobSourceType.Ashby, job.Source);
        Assert.Equal("f1e2", job.SourceJobId);
        Assert.Equal("ML Engineer", job.Title);
        Assert.True(job.Remote);
        Assert.Contains("PyTorch", job.Description);
        Assert.Equal("https://jobs.ashbyhq.com/acme/f1e2", job.ApplyUrl);
    }

    [Fact]
    public async Task Connector_throws_on_http_error()
    {
        var client = new HttpClient(new StubHttpMessageHandler("nope", HttpStatusCode.InternalServerError))
        {
            BaseAddress = new Uri("https://boards-api.greenhouse.io/")
        };
        var source = new GreenhouseJobSource(client, NullLogger<GreenhouseJobSource>.Instance);

        await Assert.ThrowsAsync<HttpRequestException>(() => source.FetchAsync("acme"));
    }
}
