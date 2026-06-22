using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace SkillRadar.Data;

/// <summary>
/// Enables `dotnet ef` commands to construct the context at design time without the API host.
/// Reads the connection string from SKILLRADAR_CONNECTION, falling back to a local default.
/// </summary>
public class DesignTimeDbContextFactory : IDesignTimeDbContextFactory<SkillRadarDbContext>
{
    public SkillRadarDbContext CreateDbContext(string[] args)
    {
        var connection = Environment.GetEnvironmentVariable("SKILLRADAR_CONNECTION")
            ?? "Host=localhost;Port=5432;Database=skillradar;Username=postgres;Password=postgres";

        var options = new DbContextOptionsBuilder<SkillRadarDbContext>()
            .UseNpgsql(connection)
            .Options;

        return new SkillRadarDbContext(options);
    }
}
