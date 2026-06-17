namespace SkillRadar.Core.Entities;

/// <summary>
/// Gold layer aggregate: how many active jobs for a given role require a given skill,
/// captured as a daily snapshot so trends can be derived later.
/// </summary>
public class SkillDemand
{
    public long Id { get; set; }

    public int RoleId { get; set; }
    public Role Role { get; set; } = null!;

    public int SkillId { get; set; }
    public Skill Skill { get; set; } = null!;

    /// <summary>Number of active jobs matching the role that require this skill.</summary>
    public int JobCount { get; set; }

    /// <summary>The day this aggregate was computed (UTC date).</summary>
    public DateOnly SnapshotDate { get; set; }
}
