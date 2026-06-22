namespace SkillRadar.Core.Entities;

/// <summary>
/// A target role (e.g. "Data Engineer") whose skill demand the dashboard reports.
/// Jobs are associated with a role when their title matches one of the
/// <see cref="TitlePatterns"/> (case-insensitive substring match).
/// </summary>
public class Role
{
    public int Id { get; set; }

    public string Name { get; set; } = string.Empty;

    /// <summary>
    /// Title substrings that qualify a job for this role, e.g. ["data engineer", "etl engineer"].
    /// Stored as a text[] column.
    /// </summary>
    public List<string> TitlePatterns { get; set; } = new();
}
