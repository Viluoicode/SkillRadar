using SkillRadar.Core.Text;

namespace SkillRadar.Tests.Text;

public class DedupHasherTests
{
    [Fact]
    public void Same_fields_produce_same_hash()
    {
        var a = DedupHasher.Compute("Stripe", "Software Engineer", "San Francisco");
        var b = DedupHasher.Compute("Stripe", "Software Engineer", "San Francisco");
        Assert.Equal(a, b);
    }

    [Fact]
    public void Normalization_ignores_case_and_punctuation()
    {
        var a = DedupHasher.Compute("Stripe", "Software Engineer", "San Francisco, CA");
        var b = DedupHasher.Compute("  stripe ", "software   engineer!", "san francisco ca");
        Assert.Equal(a, b);
    }

    [Fact]
    public void Different_company_produces_different_hash()
    {
        var a = DedupHasher.Compute("Stripe", "Software Engineer", "Remote");
        var b = DedupHasher.Compute("Plaid", "Software Engineer", "Remote");
        Assert.NotEqual(a, b);
    }

    [Fact]
    public void Null_location_is_stable()
    {
        var a = DedupHasher.Compute("Stripe", "Engineer", null);
        var b = DedupHasher.Compute("Stripe", "Engineer", "");
        Assert.Equal(a, b);
    }
}
