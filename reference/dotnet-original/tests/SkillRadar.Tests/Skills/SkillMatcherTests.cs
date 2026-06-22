using SkillRadar.Core.Skills;

namespace SkillRadar.Tests.Skills;

public class SkillMatcherTests
{
    private static SkillMatcher BuildMatcher() => new(new[]
    {
        new SkillTerms(1, "JavaScript", new[] { "JavaScript", "JS" }),
        new SkillTerms(2, "C#", new[] { "C#", "CSharp" }),
        new SkillTerms(3, ".NET", new[] { ".NET", "dotnet", "ASP.NET Core" }),
        new SkillTerms(4, "Go", new[] { "Go", "Golang" }),
        new SkillTerms(5, "C++", new[] { "C++" }),
        new SkillTerms(6, "Node.js", new[] { "Node.js", "Node" }),
        new SkillTerms(7, "Python", new[] { "Python" })
    });

    [Fact]
    public void Matches_canonical_name_and_alias()
    {
        var m = BuildMatcher();
        Assert.Contains(1, m.Match("Strong JavaScript experience required"));
        Assert.Contains(1, m.Match("We use JS heavily"));
    }

    [Fact]
    public void Matches_terms_with_special_characters()
    {
        var m = BuildMatcher();
        Assert.Contains(2, m.Match("Looking for a C# developer"));
        Assert.Contains(3, m.Match("Built on .NET and ASP.NET Core"));
        Assert.Contains(5, m.Match("Systems programming in C++"));
    }

    [Fact]
    public void Does_not_match_substring_inside_other_words()
    {
        var m = BuildMatcher();
        // "JS" must not match inside "JSON"
        Assert.DoesNotContain(1, m.Match("Experience with JSON APIs"));
        // "Go" must not match inside "Google"
        Assert.DoesNotContain(4, m.Match("Worked at Google on search"));
    }

    [Fact]
    public void Matches_standalone_short_terms()
    {
        var m = BuildMatcher();
        Assert.Contains(4, m.Match("Backend services written in Go"));
    }

    [Fact]
    public void Is_case_insensitive()
    {
        var m = BuildMatcher();
        Assert.Contains(7, m.Match("PYTHON and python and Python"));
    }

    [Fact]
    public void Prefers_longer_term_node_js_over_node()
    {
        var m = BuildMatcher();
        // Both map to skill 6, but ensure Node.js matches as a whole.
        Assert.Contains(6, m.Match("We run Node.js in production"));
    }

    [Theory]
    // A sentence-ending period (or other punctuation) must not suppress the match.
    [InlineData("Strong experience in Python.", 7)]
    [InlineData("Backend services written in Go.", 4)]
    [InlineData("Looking for a C# developer.", 2)]
    [InlineData("Systems programming in C++.", 5)]
    [InlineData("languages such as Java, Python. Extensive experience", 7)]
    public void Matches_term_immediately_followed_by_period(string text, int expectedSkillId)
    {
        var m = BuildMatcher();
        Assert.Contains(expectedSkillId, m.Match(text));
    }

    [Fact]
    public void Period_inside_term_still_matches_whole_term()
    {
        var m = BuildMatcher();
        // Dropping '.' from the boundary class must not regress dotted skill names.
        Assert.Contains(6, m.Match("We run Node.js in production"));
        Assert.Contains(6, m.Match("We run Node.js."));
        Assert.Contains(3, m.Match("Built on .NET and ASP.NET Core."));
    }

    [Fact]
    public void Returns_distinct_skill_ids()
    {
        var m = BuildMatcher();
        var result = m.Match("C# C# c# and more C#");
        Assert.Single(result);
        Assert.Contains(2, result);
    }

    [Fact]
    public void Empty_text_returns_empty()
    {
        var m = BuildMatcher();
        Assert.Empty(m.Match(""));
        Assert.Empty(m.Match(null));
    }

    // ---- Context guards for ambiguous short terms (C / R / Go) ----------------------

    private const int GoId = 4, CId = 10, RId = 11;

    private static SkillMatcher BuildGuardedMatcher() => new(
        new[]
        {
            new SkillTerms(GoId, "Go", new[] { "Go", "Golang" }),
            new SkillTerms(5, "C++", new[] { "C++" }),
            new SkillTerms(CId, "C", new[] { "C" }),
            new SkillTerms(RId, "R", new[] { "R" }),
        },
        SkillGuard.Defaults);

    [Theory]
    [InlineData("Accelerate our Go-to-Market strategy")]
    [InlineData("Drive Go-To-Market execution across teams")]
    [InlineData("Track record of Go-live readiness")]
    [InlineData("Signups, Go-lives, pipeline growth")]
    [InlineData("We deliver value as you go.")]
    public void Guard_rejects_go_false_positives(string text)
        => Assert.DoesNotContain(GoId, BuildGuardedMatcher().Match(text));

    [Theory]
    [InlineData("Backend in Go, Java, or C/C++")]
    [InlineData("Services written in Go.")]
    [InlineData("We plan to migrate our stack to Go")]
    [InlineData("Strong Golang experience")]
    public void Guard_keeps_go_true_positives(string text)
        => Assert.Contains(GoId, BuildGuardedMatcher().Match(text));

    [Theory]
    [InlineData("Relationships with C-level executives")]
    [InlineData("Present to the C-suite")]
    [InlineData("Engage C suite stakeholders")]
    [InlineData("Raised a Series C round")]
    [InlineData("Based in Washington, D.C. today")]
    public void Guard_rejects_c_false_positives(string text)
        => Assert.DoesNotContain(CId, BuildGuardedMatcher().Match(text));

    [Theory]
    [InlineData("Languages like Go, Java, C/C++")]
    [InlineData("Systems programming in C, plus Rust")]
    public void Guard_keeps_c_true_positives(string text)
        => Assert.Contains(CId, BuildGuardedMatcher().Match(text));

    [Theory]
    [InlineData("Significant R&D investment")]
    [InlineData("Monthly pay R$3.000 per month")]
    public void Guard_rejects_r_false_positives(string text)
        => Assert.DoesNotContain(RId, BuildGuardedMatcher().Match(text));

    [Theory]
    [InlineData("Statistical modeling in Python, R, or Julia")]
    [InlineData("Data analysis using SQL, R")]
    public void Guard_keeps_r_true_positives(string text)
        => Assert.Contains(RId, BuildGuardedMatcher().Match(text));

    [Fact]
    public void Guard_records_skill_when_any_occurrence_is_valid()
    {
        // First mention is a false positive (GTM), second is a real language mention.
        var result = BuildGuardedMatcher().Match("Our Go-to-Market plan. Backend in Go and Java.");
        Assert.Contains(GoId, result);
    }

    // ---- Newly added dictionary terms (multi-word, acronyms, prefix collisions) -------

    [Fact]
    public void Matches_multiword_terms_and_aliases()
    {
        var m = new SkillMatcher(new[]
        {
            new SkillTerms(20, "Delta Lake", new[] { "Delta Lake" }),
            new SkillTerms(21, "Vector Database", new[] { "Vector Database", "vector store", "vector search" }),
            new SkillTerms(22, "RAG", new[] { "RAG", "Retrieval-Augmented Generation" }),
        });

        Assert.Contains(20, m.Match("Build pipelines on Delta Lake at scale"));
        Assert.Contains(21, m.Match("Experience with a vector store for embeddings"));
        Assert.Contains(22, m.Match("Familiarity with RAG pipelines"));
        Assert.Contains(22, m.Match("using Retrieval-Augmented Generation"));
    }

    [Fact]
    public void Longer_term_wins_github_actions_over_github()
    {
        // "GitHub Actions" and "GitHub" are distinct skills; the longer term must win at its
        // position so a CI mention is not also miscounted as the platform.
        var m = new SkillMatcher(new[]
        {
            new SkillTerms(30, "GitHub", new[] { "GitHub" }),
            new SkillTerms(31, "GitHub Actions", new[] { "GitHub Actions" }),
        });

        var ci = m.Match("CI runs on GitHub Actions");
        Assert.Contains(31, ci);
        Assert.DoesNotContain(30, ci);

        var platform = m.Match("Code hosted on GitHub");
        Assert.Contains(30, platform);
        Assert.DoesNotContain(31, platform);
    }
}
