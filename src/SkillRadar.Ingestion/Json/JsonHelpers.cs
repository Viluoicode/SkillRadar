using System.Text.Json;

namespace SkillRadar.Ingestion.Json;

/// <summary>Defensive accessors for reading loosely-typed ATS JSON payloads.</summary>
internal static class JsonHelpers
{
    public static string? GetString(this JsonElement el, string property)
    {
        if (el.ValueKind == JsonValueKind.Object &&
            el.TryGetProperty(property, out var v) &&
            v.ValueKind == JsonValueKind.String)
        {
            return v.GetString();
        }
        return null;
    }

    public static bool GetBool(this JsonElement el, string property)
    {
        if (el.ValueKind == JsonValueKind.Object && el.TryGetProperty(property, out var v))
        {
            return v.ValueKind switch
            {
                JsonValueKind.True => true,
                JsonValueKind.False => false,
                _ => false
            };
        }
        return false;
    }

    /// <summary>Reads a property as a raw id string, accepting either JSON string or number.</summary>
    public static string? GetId(this JsonElement el, string property)
    {
        if (el.ValueKind != JsonValueKind.Object || !el.TryGetProperty(property, out var v))
            return null;

        return v.ValueKind switch
        {
            JsonValueKind.String => v.GetString(),
            JsonValueKind.Number => v.GetRawText(),
            _ => null
        };
    }

    public static bool TryGetChild(this JsonElement el, string property, out JsonElement child)
    {
        if (el.ValueKind == JsonValueKind.Object && el.TryGetProperty(property, out child))
            return true;
        child = default;
        return false;
    }
}
