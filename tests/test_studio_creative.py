from market_intel.studio_creative.brief import _fact_rows
from market_intel.studio_creative.commerce import (
    listing_copies,
)
from market_intel.studio_creative.commerce import (
    test_plan as build_test_plan,
)
from market_intel.studio_creative.copy import (
    build_script,
    claim_guard,
    concepts,
    preflight,
    variants_for,
)


def sample():
    product = {
        "handle": "example",
        "category": "Sunscreen",
        "title": "Gel Sunscreen SPF 50+",
        "url": "https://www.dotandkey.com/products/example",
        "spf": "50+",
        "size": "45 ml",
        "hero_ingredient": "Watermelon",
        "ingredients": ["Watermelon"],
        "local_images": [],
        "description": "A lightweight formula for oily skin. Instant cooling with watermelon. Apply before stepping out. Suggested Routine Another product treats acne.",
    }
    facts = _fact_rows(product)
    return {
        "product": product,
        "claim_sources": facts,
        "allowed_claims": [r["text"] for r in facts],
        "audience": {"skin_types": ["Oily"], "top_objections": [], "top_desires": []},
        "search_terms": ["Sunscreen", "Watermelon"],
    }


def test_claim_guard_handles_invented_claims_mismatched_spf_and_other_products():
    brief = sample()
    assert claim_guard(["SPF 50+", "Explore the formula."], brief)["status"] == "pass"
    for line in (
        "SPF 50",
        "SPF 90",
        "100% safe",
        "Explore the formula. Cures acne.",
        "Removes all oily skin",
    ):
        assert claim_guard([line], brief)["status"] == "fail"
    assert all("treats" not in row["text"] for row in brief["claim_sources"])


def test_reference_rhythm_preserved_and_variants_trace_to_patterns(monkeypatch):
    monkeypatch.setattr(
        "market_intel.studio_creative.copy.compose_json",
        lambda *args, **kwargs: (None, {"status": "unavailable"}),
    )
    brief = sample()
    pattern = {
        "id": "p1",
        "name": "Product demonstration",
        "winning_spec": {"length_iqr": [12, 14], "cuts_per_second_median": 0.5},
    }
    cs = concepts(brief, [pattern])
    assert len(cs) == 3
    reference = {"shots": [{"duration": 1.2} for _ in range(12)]}
    script = build_script(brief, [pattern], cs[0], reference=reference)
    assert len(script["shots"]) == 12 and all(
        s["duration"] == 1.2 for s in script["shots"]
    )
    assert all(s["pattern_ref"] == "p1" for s in script["shots"])
    assert len(variants_for(script, cs[0], brief)) == 6
    score = preflight(script, pattern, brief)
    assert next(c for c in score["checks"] if c["id"] == "pace")["status"] == "fail"
    assert len(build_test_plan(variants_for(script, cs[0], brief))["first_three"]) == 3


def test_listing_fallback_has_five_locked_bullets_and_market_limits(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "market_intel.studio_creative.commerce.compose_json",
        lambda *args, **kwargs: (
            {"listings": [{"market": "Nykaa", "bullet_ids": ["fabricated"]}]},
            {"status": "generated"},
        ),
    )
    brief = sample()
    listings = listing_copies(tmp_path, brief)
    assert len(listings) == 3
    for row in listings:
        assert row["status"] == "ready" and len(set(row["bullets"])) == 5
        assert all(
            line.rstrip(".") in brief["allowed_claims"] for line in row["bullets"]
        )
        assert row["keyword_bytes"] <= row["limits"]["keyword_bytes"]
