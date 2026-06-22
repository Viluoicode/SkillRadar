namespace SkillRadar.Core.Entities;

/// <summary>Gold layer: a skill extracted from a job posting (many-to-many join).</summary>
public class JobSkill
{
    public long JobId { get; set; }
    public Job Job { get; set; } = null!;

    public int SkillId { get; set; }
    public Skill Skill { get; set; } = null!;
}
