using Microsoft.EntityFrameworkCore;
using SkillRadar.Core.Skills;
using SkillRadar.Data;

namespace SkillRadar.Ingestion;

/// <summary>
/// Builds a <see cref="SkillMatcher"/> from the persisted skill dictionary (skills + aliases).
/// The canonical name is always a matchable term alongside every alias.
/// </summary>
public class SkillExtractor(SkillRadarDbContext db)
{
    public async Task<SkillMatcher> BuildMatcherAsync(CancellationToken ct = default)
    {
        var skills = await db.Skills
            .Select(s => new
            {
                s.Id,
                s.Name,
                Aliases = s.Aliases.Select(a => a.Alias).ToList()
            })
            .ToListAsync(ct);

        var terms = skills.Select(s =>
        {
            var allTerms = new List<string>(s.Aliases.Count + 1) { s.Name };
            allTerms.AddRange(s.Aliases);
            return new SkillTerms(s.Id, s.Name, allTerms);
        });

        return new SkillMatcher(terms, SkillGuard.Defaults);
    }
}
