using Hangfire;
using Hangfire.PostgreSql;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;
using SkillRadar.Api.Endpoints;
using SkillRadar.Data;
using SkillRadar.Data.Seeding;
using SkillRadar.Ingestion;

var builder = WebApplication.CreateBuilder(args);

// Connection string: env var wins (matches the EF design-time factory), then appsettings.
var connectionString = Environment.GetEnvironmentVariable("SKILLRADAR_CONNECTION")
    ?? builder.Configuration.GetConnectionString("SkillRadar")
    ?? throw new InvalidOperationException("No database connection string configured.");

// Resolve the data-file paths relative to the content root when not absolute.
var ingestionSection = builder.Configuration.GetSection("Ingestion");
ResolveDataPaths(ingestionSection, builder.Environment.ContentRootPath);

builder.Services.AddDbContext<SkillRadarDbContext>(opt => opt.UseNpgsql(connectionString));
builder.Services.AddScoped<DbSeeder>();
builder.Services.AddIngestion(builder.Configuration);

const string SpaCors = "spa";
builder.Services.AddCors(o => o.AddPolicy(SpaCors, p =>
{
    var origins = builder.Configuration.GetSection("Cors:Origins").Get<string[]>()
        ?? new[] { "http://localhost:5173" };
    p.WithOrigins(origins).AllowAnyHeader().AllowAnyMethod();
}));

builder.Services.AddHangfire(cfg => cfg
    .SetDataCompatibilityLevel(CompatibilityLevel.Version_180)
    .UseSimpleAssemblyNameTypeSerializer()
    .UseRecommendedSerializerSettings()
    .UsePostgreSqlStorage(o => o.UseNpgsqlConnection(connectionString)));
builder.Services.AddHangfireServer();

builder.Services.AddOpenApi();

var app = builder.Build();

// Apply migrations, seed the dictionary/roles, and register the recurring ingestion job.
await InitializeAsync(app);

if (app.Environment.IsDevelopment())
    app.MapOpenApi();

app.UseCors(SpaCors);

app.UseHangfireDashboard("/hangfire");
app.MapSkillRadarApi();

app.Run();

return;

static void ResolveDataPaths(IConfigurationSection ingestion, string contentRoot)
{
    foreach (var key in new[] { "SourcesPath", "SkillsSeedPath" })
    {
        var value = ingestion[key];
        if (!string.IsNullOrWhiteSpace(value) && !Path.IsPathRooted(value))
            ingestion[key] = Path.GetFullPath(Path.Combine(contentRoot, value));
    }
}

static async Task InitializeAsync(WebApplication app)
{
    using var scope = app.Services.CreateScope();
    var sp = scope.ServiceProvider;

    var db = sp.GetRequiredService<SkillRadarDbContext>();
    await db.Database.MigrateAsync();

    var options = sp.GetRequiredService<IOptions<IngestionOptions>>().Value;
    var seeder = sp.GetRequiredService<DbSeeder>();
    await seeder.SeedAsync(options.SkillsSeedPath);

    // Recurring ingestion on the configured cron.
    var recurring = sp.GetRequiredService<IRecurringJobManager>();
    recurring.AddOrUpdate<IngestionJob>(
        "ingest-all-sources",
        job => job.RunAsync("Scheduled", CancellationToken.None),
        options.Cron);
}
