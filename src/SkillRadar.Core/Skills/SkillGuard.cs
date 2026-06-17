using System.Text.RegularExpressions;

namespace SkillRadar.Core.Skills;

/// <summary>
/// A precision guard for an ambiguous skill term. After the term matches, the occurrence is
/// rejected when the immediately surrounding text matches a "this isn't the skill" pattern.
/// This lets short, word-like terms ("C", "R", "Go") stay matchable inside real language lists
/// while suppressing common false positives ("C-level", "R&amp;D", "Go-to-Market").
/// </summary>
public sealed class SkillGuard
{
    private readonly Regex? _rejectBefore;
    private readonly Regex? _rejectAfter;

    /// <summary>The (case-insensitive) surface term this guard applies to, e.g. "Go".</summary>
    public string Term { get; }

    /// <param name="term">The surface term the guard applies to (matched case-insensitively).</param>
    /// <param name="rejectBefore">Anchor with <c>$</c>; tested against the text ending at the match start.</param>
    /// <param name="rejectAfter">Anchor with <c>^</c>; tested against the text starting at the match end.</param>
    public SkillGuard(string term, string? rejectBefore = null, string? rejectAfter = null)
    {
        Term = term;
        const RegexOptions opts =
            RegexOptions.IgnoreCase | RegexOptions.Compiled | RegexOptions.CultureInvariant;
        if (rejectBefore is not null) _rejectBefore = new Regex(rejectBefore, opts);
        if (rejectAfter is not null) _rejectAfter = new Regex(rejectAfter, opts);
    }

    /// <summary>True when the match at [<paramref name="start"/>, start+<paramref name="length"/>) is a false positive.</summary>
    public bool Rejects(string text, int start, int length)
    {
        // '^' in _rejectAfter anchors to the start of the trailing span, so this is cheap.
        if (_rejectAfter is not null && _rejectAfter.IsMatch(text.AsSpan(start + length)))
            return true;

        if (_rejectBefore is not null)
        {
            // A short tail is enough context and keeps the '$'-anchored scan bounded.
            var tail = Math.Min(16, start);
            if (_rejectBefore.IsMatch(text.AsSpan(start - tail, tail)))
                return true;
        }

        return false;
    }

    /// <summary>
    /// Built-in guards for the ambiguous single/short terms in the seeded dictionary, calibrated
    /// against real ATS descriptions:
    /// <list type="bullet">
    /// <item>"C": exec-speak ("C-level", "C-suite", "C suite"), funding ("Series C"), places
    /// ("D.C."), and foreign text ("C'est").</item>
    /// <item>"R": "R&amp;D" and "R$" (Brazilian Real).</item>
    /// <item>"Go": "Go-to-Market", "Go-live(s)", and the verb ("as you go").</item>
    /// </list>
    /// True positives — language lists like "Go, Java, C/C++" or "Python, R, or …" — are kept.
    /// </summary>
    public static IReadOnlyList<SkillGuard> Defaults { get; } = new[]
    {
        new SkillGuard("C",
            rejectBefore: @"([A-Za-z]\.|\bseries )$",
            rejectAfter: @"^([\s‑-]?(?:level|suite)\b|['’])"),
        new SkillGuard("R",
            rejectAfter: @"^[&$]"),
        new SkillGuard("Go",
            rejectBefore: @"\byou $",
            rejectAfter: @"^-(?:to-market|live)"),
    };
}
