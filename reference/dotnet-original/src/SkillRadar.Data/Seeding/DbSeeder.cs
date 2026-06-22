using System.Text.Json;
using Microsoft.EntityFrameworkCore;
using SkillRadar.Core.Entities;

namespace SkillRadar.Data.Seeding;

/// <summary>
/// Idempotently applies pending migrations and loads the seed skill dictionary and roles.
/// Safe to call on every startup: existing skills/roles are left untouched and only new
/// entries are added.
/// </summary>
public class DbSeeder(SkillRadarDbContext db)
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    /// <summary>The roles seeded on a fresh database (modeled for many; MVP focuses on one).</summary>
    public static readonly IReadOnlyList<(string Name, string[] Patterns)> DefaultRoles = new[]
    {
        ("Backend Engineer", new[] { "backend engineer", "back-end engineer", "backend developer", "backend software engineer" }),
        ("Frontend Engineer", new[] { "frontend engineer", "front-end engineer", "frontend developer", "ui engineer" }),
        ("Full Stack Engineer", new[] { "full stack", "fullstack", "full-stack engineer" }),
        ("Data Engineer", new[] { "data engineer", "etl engineer", "analytics engineer" }),
        ("Data Scientist", new[] { "data scientist", "machine learning scientist" }),
        ("Machine Learning Engineer", new[] { "machine learning engineer", "ml engineer", "ai engineer" }),
        ("DevOps Engineer", new[] { "devops", "site reliability", "sre", "platform engineer", "infrastructure engineer" }),
        ("Mobile Engineer", new[] { "mobile engineer", "ios engineer", "android engineer", "mobile developer" })
    };

    public async Task SeedAsync(string skillsSeedPath, CancellationToken ct = default)
    {
        await SeedSkillsAsync(skillsSeedPath, ct);
        await SeedRolesAsync(ct);
    }

    private async Task SeedSkillsAsync(string skillsSeedPath, CancellationToken ct)
    {
        if (!File.Exists(skillsSeedPath))
            throw new FileNotFoundException($"Skill seed file not found: {skillsSeedPath}");

        await using var stream = File.OpenRead(skillsSeedPath);
        var seed = await JsonSerializer.DeserializeAsync<SkillSeedFile>(stream, JsonOptions, ct)
            ?? new SkillSeedFile();

        var existingSkills = await db.Skills
            .Select(s => s.Name)
            .ToListAsync(ct);
        var existingSkillSet = new HashSet<string>(existingSkills, StringComparer.OrdinalIgnoreCase);

        var existingAliases = await db.SkillAliases
            .Select(a => a.Alias)
            .ToListAsync(ct);
        var existingAliasSet = new HashSet<string>(existingAliases, StringComparer.OrdinalIgnoreCase);

        foreach (var item in seed.Skills)
        {
            if (existingSkillSet.Contains(item.Name))
                continue;

            var skill = new Skill { Name = item.Name, Category = item.Category };
            // The canonical name is always a matchable term; add distinct aliases too.
            foreach (var alias in item.Aliases.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                if (existingAliasSet.Add(alias))
                    skill.Aliases.Add(new SkillAlias { Alias = alias });
            }

            db.Skills.Add(skill);
            existingSkillSet.Add(item.Name);
        }

        await db.SaveChangesAsync(ct);
    }

    private async Task SeedRolesAsync(CancellationToken ct)
    {
        var existingRoles = await db.Roles
            .Select(r => r.Name)
            .ToListAsync(ct);
        var existingRoleSet = new HashSet<string>(existingRoles, StringComparer.OrdinalIgnoreCase);

        foreach (var (name, patterns) in DefaultRoles)
        {
            if (existingRoleSet.Contains(name))
                continue;

            db.Roles.Add(new Role { Name = name, TitlePatterns = patterns.ToList() });
        }

        await db.SaveChangesAsync(ct);
    }
}
