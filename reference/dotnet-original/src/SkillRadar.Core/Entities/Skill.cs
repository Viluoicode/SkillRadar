namespace SkillRadar.Core.Entities;

/// <summary>Gold layer: a canonical skill from the seed dictionary.</summary>
public class Skill
{
    public int Id { get; set; }

    /// <summary>Canonical display name, e.g. "JavaScript".</summary>
    public string Name { get; set; } = string.Empty;

    /// <summary>Grouping category, e.g. "Language", "Cloud", "Database".</summary>
    public string Category { get; set; } = string.Empty;

    public ICollection<SkillAlias> Aliases { get; set; } = new List<SkillAlias>();
    public ICollection<JobSkill> JobSkills { get; set; } = new List<JobSkill>();
}
