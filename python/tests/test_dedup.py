"""Port of the .NET DedupHasherTests."""

from skillradar.common.dedup import compute_dedup_hash


def test_same_fields_produce_same_hash():
    a = compute_dedup_hash("Stripe", "Software Engineer", "San Francisco")
    b = compute_dedup_hash("Stripe", "Software Engineer", "San Francisco")
    assert a == b


def test_normalization_ignores_case_and_punctuation():
    a = compute_dedup_hash("Stripe", "Software Engineer", "San Francisco, CA")
    b = compute_dedup_hash("  stripe ", "software   engineer!", "san francisco ca")
    assert a == b


def test_different_company_produces_different_hash():
    a = compute_dedup_hash("Stripe", "Software Engineer", "Remote")
    b = compute_dedup_hash("Plaid", "Software Engineer", "Remote")
    assert a != b


def test_null_location_is_stable():
    a = compute_dedup_hash("Stripe", "Engineer", None)
    b = compute_dedup_hash("Stripe", "Engineer", "")
    assert a == b
