using System.Security.Cryptography;
using System.Text;

namespace SkillRadar.Core.Text;

/// <summary>
/// Builds the normalized content hash used as the cross-source dedup fallback.
/// Two postings of the same role (same company, title and location) produce the same hash
/// even when they originate from different boards or sources.
/// </summary>
public static class DedupHasher
{
    public static string Compute(string company, string title, string? location)
    {
        var key = string.Join(
            '|',
            TextNormalizer.NormalizeForKey(company),
            TextNormalizer.NormalizeForKey(title),
            TextNormalizer.NormalizeForKey(location));

        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(key));
        return Convert.ToHexString(bytes);
    }
}
