using System.Text.RegularExpressions;

namespace SkillRadar.Core.Skills;

/// <summary>A canonical skill plus every surface form (name + aliases) that should match it.</summary>
public sealed record SkillTerms(int SkillId, string CanonicalName, IReadOnlyCollection<string> Terms);

/// <summary>
/// Rule-based, dictionary-driven skill extractor. Compiles all skill terms into a single
/// case-insensitive regex with token boundaries that respect characters common in tech terms
/// (so "C#", ".NET", "C++", "Node.js" match, while "Go" does not match inside "Google" and
/// "JS" does not match inside "JSON").
/// </summary>
public sealed class SkillMatcher
{
    // Boundary characters: a term only matches when it is not flanked by one of these, giving
    // word-style boundaries that still treat #, + as part of a token (so "JS" doesn't match in
    // "JSON", nor "C" in "C#"). Crucially '.' is NOT a boundary char: a literal dot inside a
    // skill name is matched by the escaped term itself ("Node.js", ".NET"), so excluding it here
    // lets a term still match when followed by a sentence-ending period ("...we use Python.").
    private const string TokenChar = "A-Za-z0-9+#";

    private readonly Regex _regex;
    private readonly Dictionary<string, int> _termToSkillId;
    private readonly Dictionary<string, SkillGuard> _guards;

    public SkillMatcher(IEnumerable<SkillTerms> skills, IEnumerable<SkillGuard>? guards = null)
    {
        _termToSkillId = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        _guards = (guards ?? Enumerable.Empty<SkillGuard>())
            .ToDictionary(g => g.Term, StringComparer.OrdinalIgnoreCase);

        foreach (var skill in skills)
        {
            foreach (var term in skill.Terms)
            {
                var trimmed = term.Trim();
                if (trimmed.Length == 0)
                    continue;
                // First definition of a term wins; ignore duplicate alias collisions.
                _termToSkillId.TryAdd(trimmed, skill.SkillId);
            }
        }

        if (_termToSkillId.Count == 0)
        {
            // A regex that never matches.
            _regex = new Regex("(?!)", RegexOptions.Compiled);
            return;
        }

        // Longer terms first so "Node.js" wins over "Node" at the same position.
        var alternation = string.Join(
            '|',
            _termToSkillId.Keys
                .OrderByDescending(t => t.Length)
                .Select(Regex.Escape));

        var pattern = $"(?<![{TokenChar}])(?:{alternation})(?![{TokenChar}])";
        _regex = new Regex(pattern, RegexOptions.Compiled | RegexOptions.IgnoreCase);
    }

    /// <summary>Returns the distinct skill ids mentioned anywhere in <paramref name="text"/>.</summary>
    public IReadOnlySet<int> Match(string? text)
    {
        var found = new HashSet<int>();
        if (string.IsNullOrWhiteSpace(text))
            return found;

        foreach (Match m in _regex.Matches(text))
        {
            if (!_termToSkillId.TryGetValue(m.Value, out var skillId))
                continue;

            // An ambiguous term ("C", "R", "Go") only counts when its context isn't a known
            // false positive ("C-level", "R&D", "Go-to-Market"). The skill is still recorded if
            // any other occurrence in the text passes.
            if (_guards.TryGetValue(m.Value, out var guard) && guard.Rejects(text, m.Index, m.Length))
                continue;

            found.Add(skillId);
        }

        return found;
    }
}
