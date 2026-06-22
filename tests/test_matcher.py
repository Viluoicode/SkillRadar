"""Port of the .NET SkillMatcherTests (matcher boundaries + ambiguous-term guards)."""

import pytest

from skillradar.domain.skills.guards import DEFAULT_GUARDS
from skillradar.domain.skills.matcher import SkillMatcher, SkillTerms


def build_matcher() -> SkillMatcher:
    return SkillMatcher(
        [
            SkillTerms(1, "JavaScript", ("JavaScript", "JS")),
            SkillTerms(2, "C#", ("C#", "CSharp")),
            SkillTerms(3, ".NET", (".NET", "dotnet", "ASP.NET Core")),
            SkillTerms(4, "Go", ("Go", "Golang")),
            SkillTerms(5, "C++", ("C++",)),
            SkillTerms(6, "Node.js", ("Node.js", "Node")),
            SkillTerms(7, "Python", ("Python",)),
        ]
    )


def test_matches_canonical_name_and_alias():
    m = build_matcher()
    assert 1 in m.match("Strong JavaScript experience required")
    assert 1 in m.match("We use JS heavily")


def test_matches_terms_with_special_characters():
    m = build_matcher()
    assert 2 in m.match("Looking for a C# developer")
    assert 3 in m.match("Built on .NET and ASP.NET Core")
    assert 5 in m.match("Systems programming in C++")


def test_does_not_match_substring_inside_other_words():
    m = build_matcher()
    assert 1 not in m.match("Experience with JSON APIs")  # JS not inside JSON
    assert 4 not in m.match("Worked at Google on search")  # Go not inside Google


def test_matches_standalone_short_terms():
    assert 4 in build_matcher().match("Backend services written in Go")


def test_is_case_insensitive():
    assert 7 in build_matcher().match("PYTHON and python and Python")


def test_prefers_longer_term_node_js_over_node():
    assert 6 in build_matcher().match("We run Node.js in production")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Strong experience in Python.", 7),
        ("Backend services written in Go.", 4),
        ("Looking for a C# developer.", 2),
        ("Systems programming in C++.", 5),
        ("languages such as Java, Python. Extensive experience", 7),
    ],
)
def test_matches_term_immediately_followed_by_period(text, expected):
    assert expected in build_matcher().match(text)


def test_period_inside_term_still_matches_whole_term():
    m = build_matcher()
    assert 6 in m.match("We run Node.js in production")
    assert 6 in m.match("We run Node.js.")
    assert 3 in m.match("Built on .NET and ASP.NET Core.")


def test_returns_distinct_skill_ids():
    result = build_matcher().match("C# C# c# and more C#")
    assert result == {2}


def test_empty_text_returns_empty():
    m = build_matcher()
    assert m.match("") == set()
    assert m.match(None) == set()


# ---- Context guards for ambiguous short terms (C / R / Go) ----------------------

GO_ID, C_ID, R_ID = 4, 10, 11


def build_guarded() -> SkillMatcher:
    return SkillMatcher(
        [
            SkillTerms(GO_ID, "Go", ("Go", "Golang")),
            SkillTerms(5, "C++", ("C++",)),
            SkillTerms(C_ID, "C", ("C",)),
            SkillTerms(R_ID, "R", ("R",)),
        ],
        DEFAULT_GUARDS,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Accelerate our Go-to-Market strategy",
        "Drive Go-To-Market execution across teams",
        "Track record of Go-live readiness",
        "Signups, Go-lives, pipeline growth",
        "We deliver value as you go.",
    ],
)
def test_guard_rejects_go_false_positives(text):
    assert GO_ID not in build_guarded().match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Backend in Go, Java, or C/C++",
        "Services written in Go.",
        "We plan to migrate our stack to Go",
        "Strong Golang experience",
    ],
)
def test_guard_keeps_go_true_positives(text):
    assert GO_ID in build_guarded().match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Relationships with C-level executives",
        "Present to the C-suite",
        "Engage C suite stakeholders",
        "Raised a Series C round",
        "Based in Washington, D.C. today",
    ],
)
def test_guard_rejects_c_false_positives(text):
    assert C_ID not in build_guarded().match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Languages like Go, Java, C/C++",
        "Systems programming in C, plus Rust",
    ],
)
def test_guard_keeps_c_true_positives(text):
    assert C_ID in build_guarded().match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Significant R&D investment",
        "Monthly pay R$3.000 per month",
    ],
)
def test_guard_rejects_r_false_positives(text):
    assert R_ID not in build_guarded().match(text)


@pytest.mark.parametrize(
    "text",
    [
        "Statistical modeling in Python, R, or Julia",
        "Data analysis using SQL, R",
    ],
)
def test_guard_keeps_r_true_positives(text):
    assert R_ID in build_guarded().match(text)


def test_guard_records_skill_when_any_occurrence_is_valid():
    result = build_guarded().match("Our Go-to-Market plan. Backend in Go and Java.")
    assert GO_ID in result


def test_matches_multiword_terms_and_aliases():
    m = SkillMatcher(
        [
            SkillTerms(20, "Delta Lake", ("Delta Lake",)),
            SkillTerms(21, "Vector Database", ("Vector Database", "vector store", "vector search")),
            SkillTerms(22, "RAG", ("RAG", "Retrieval-Augmented Generation")),
        ]
    )
    assert 20 in m.match("Build pipelines on Delta Lake at scale")
    assert 21 in m.match("Experience with a vector store for embeddings")
    assert 22 in m.match("Familiarity with RAG pipelines")
    assert 22 in m.match("using Retrieval-Augmented Generation")


def test_longer_term_wins_github_actions_over_github():
    m = SkillMatcher(
        [
            SkillTerms(30, "GitHub", ("GitHub",)),
            SkillTerms(31, "GitHub Actions", ("GitHub Actions",)),
        ]
    )
    ci = m.match("CI runs on GitHub Actions")
    assert 31 in ci and 30 not in ci

    platform = m.match("Code hosted on GitHub")
    assert 30 in platform and 31 not in platform
