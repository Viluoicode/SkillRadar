namespace SkillRadar.Core.Entities;

/// <summary>
/// An alternate surface form that maps to a canonical <see cref="Skill"/>,
/// e.g. "JS" -> JavaScript, "k8s" -> Kubernetes. Matched case-insensitively
/// on word boundaries.
/// </summary>
public class SkillAlias
{
    public int Id { get; set; }
    public int SkillId { get; set; }
    public Skill Skill { get; set; } = null!;

    /// <summary>The alias text as it appears in postings (matched case-insensitively).</summary>
    public string Alias { get; set; } = string.Empty;
}
