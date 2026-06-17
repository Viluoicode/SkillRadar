namespace SkillRadar.Data.Seeding;

/// <summary>Deserialization shape for an entry in data/skills.seed.json.</summary>
public record SkillSeed
{
    public required string Name { get; init; }
    public required string Category { get; init; }
    public List<string> Aliases { get; init; } = new();
}

/// <summary>Root of data/skills.seed.json.</summary>
public record SkillSeedFile
{
    public List<SkillSeed> Skills { get; init; } = new();
}
