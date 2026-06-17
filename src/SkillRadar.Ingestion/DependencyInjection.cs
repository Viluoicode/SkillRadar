using System.Net.Http.Headers;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using SkillRadar.Core.Ingestion;
using SkillRadar.Ingestion.Sources;

namespace SkillRadar.Ingestion;

public static class DependencyInjection
{
    /// <summary>
    /// Registers the ingestion pipeline and the three ATS connectors as typed HttpClients,
    /// each with a standard resilience pipeline (retry + exponential backoff + jitter, timeout,
    /// circuit breaker) to absorb rate limits and transient source failures.
    /// </summary>
    public static IServiceCollection AddIngestion(this IServiceCollection services, IConfiguration config)
    {
        services.Configure<IngestionOptions>(config.GetSection("Ingestion"));

        services.AddSingleton(TimeProvider.System);
        services.AddSingleton<SourceCatalogProvider>();
        services.AddScoped<JobSourceRegistry>();
        services.AddScoped<SkillExtractor>();
        services.AddScoped<IngestionPipeline>();
        services.AddScoped<IngestionJob>();

        AddConnector<GreenhouseJobSource>(services, "https://boards-api.greenhouse.io/");
        AddConnector<LeverJobSource>(services, "https://api.lever.co/");
        AddConnector<AshbyJobSource>(services, "https://api.ashbyhq.com/");

        return services;
    }

    private static void AddConnector<TSource>(IServiceCollection services, string baseAddress)
        where TSource : class, IJobSource
    {
        services.AddHttpClient<TSource>(client =>
            {
                client.BaseAddress = new Uri(baseAddress);
                client.Timeout = TimeSpan.FromSeconds(30);
                client.DefaultRequestHeaders.UserAgent.Add(
                    new ProductInfoHeaderValue("SkillRadar", "1.0"));
                client.DefaultRequestHeaders.Accept.Add(
                    new MediaTypeWithQualityHeaderValue("application/json"));
            })
            .AddStandardResilienceHandler();

        // Expose the typed connector through the IJobSource collection used by the registry.
        services.AddScoped<IJobSource>(sp => sp.GetRequiredService<TSource>());
    }
}
