using System.Net;
using System.Text.RegularExpressions;

namespace SkillRadar.Core.Text;

/// <summary>Helpers for cleaning ATS payload text and normalizing fields for dedup.</summary>
public static partial class TextNormalizer
{
    [GeneratedRegex("<[^>]+>", RegexOptions.Singleline)]
    private static partial Regex HtmlTagRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex WhitespaceRegex();

    [GeneratedRegex("[^a-z0-9 ]")]
    private static partial Regex NonAlphanumericRegex();

    /// <summary>
    /// Converts ATS HTML (which may be entity-encoded, e.g. Greenhouse's "content") to plain
    /// text: decode entities first so encoded tags become real tags, then strip tags and
    /// collapse whitespace.
    /// </summary>
    public static string StripHtml(string? html)
    {
        if (string.IsNullOrWhiteSpace(html))
            return string.Empty;

        var decoded = WebUtility.HtmlDecode(html);
        var withoutTags = HtmlTagRegex().Replace(decoded, " ");
        return WhitespaceRegex().Replace(withoutTags, " ").Trim();
    }

    /// <summary>
    /// Produces a stable comparison key: lower-cased, punctuation removed, whitespace collapsed.
    /// Used to build the cross-source dedup hash from (company + title + location).
    /// </summary>
    public static string NormalizeForKey(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
            return string.Empty;

        var lowered = value.Trim().ToLowerInvariant();
        var cleaned = NonAlphanumericRegex().Replace(lowered, " ");
        return WhitespaceRegex().Replace(cleaned, " ").Trim();
    }
}
