from datetime import date

from market_intel.recommendations import build_recommendations
from market_intel.swot import build_swot

AS_OF = date(2026, 11, 21)
BRANDS = ["Dot & Key", "A", "B", "C", "D", "E"]


def _cohort():
    raw = {
        "category": "Sunscreen",
        "products": [],
        "listings": [],
        "brand_signals": [],
        "competitor_set": [],
    }
    metrics = {"products": {}, "brands": {}}
    for i, b in enumerate(BRANDS):
        ref = str(i)
        raw["products"].append(
            {"product_ref": ref, "brand": b, "title": f"{b} Sunscreen"}
        )
        raw["listings"].append(
            {"product_ref": ref, "url": f"https://source.test/{ref}"}
        )
        if i:
            raw["competitor_set"].append({"product_ref": ref})
        aspect = {
            "validated": True,
            "claim_eligible": True,
            "mentions": 50,
            "directional_n": 50,
            "nss": 0.8 if i == 0 else -0.3,
            "wilson": [0.78, 0.97] if i == 0 else [0.22, 0.50],
            "mention_rate": 0.3,
            "complaint_lift": None,
            "evidence": [{"quote": f"Review {i}", "url": f"https://source.test/{ref}"}],
        }
        stats = {
            "rating": {
                "bayesian": 4.5 if i == 0 else 4.1,
                "basis": "listing_rating_counts",
                "n": 100,
                "by_variant": {},
            },
            "aspects": {"hydration": aspect},
            "velocity": {"per_day": None, "n": 0},
            "price": {"by_unit": {}, "n": 1, "discount_change_30d": None},
        }
        metrics["brands"][b] = stats
        metrics["products"][ref] = stats
    return raw, metrics


def test_uses_share_scale_for_wilson_and_gates_small_or_unvalidated_groups():
    raw, m = _cohort()
    result = build_swot(raw, m, {}, {}, AS_OF)
    assert {r["rule"] for r in result["strength"]} == {"aspect_advantage", "top_rating"}
    assert {r["rule"] for r in result["opportunity"]} == {
        "peer_pain",
        "messaging_advantage",
    }
    for brand in BRANDS[2:]:
        m["brands"][brand]["aspects"]["hydration"]["claim_eligible"] = False
    m["brands"]["E"]["rating"]["basis"] = "sampled_reviews"
    result = build_swot(raw, m, {}, {}, AS_OF)
    assert result["strength"] == [] and result["opportunity"] == []


def test_channel_gap_same_variant_boundaries_and_traceable_actions():
    raw, m = _cohort()
    m["products"]["0"]["rating"]["by_variant"] = {
        "sku80": {
            "amazon": {"mean": 4.0, "n": 120, "urls": ["https://source.test/a"]},
            "flipkart": {"mean": 4.3, "n": 80, "urls": ["https://source.test/f"]},
        }
    }
    result = build_swot(raw, m, {}, {}, AS_OF)
    (row,) = result["weakness"]
    assert row["metric_values"]["variant_sku"] == "sku80" and row["n"] == 200
    action = next(
        r for r in build_recommendations(result, {}, {}) if r["type"] == "Marketplace"
    )
    assert action["trigger_ids"] == [row["id"]]
    group = m["products"]["0"]["rating"]["by_variant"]
    group["sku50"] = {"flipkart": group["sku80"].pop("flipkart")}
    assert not build_swot(raw, m, {}, {}, AS_OF)["weakness"]


def test_launch_dates_company_momentum_and_actual_discount_comparisons():
    raw, m = _cohort()
    raw["brand_signals"] = [
        {
            "brand": "A",
            "source": "crustdata_company",
            "domain": "a.test",
            "captured_at": "2026-11-20",
            "followers": {"qoq_percent": 24},
        }
    ]
    launch = {
        "title": "A sunscreen",
        "url": "https://a.test/new",
        "brand": "A",
        "product_ref": "shopify:a",
        "category": "Sunscreen",
        "date": "2026-11-01",
        "launch_basis": "recent_created_at_on_baseline",
    }
    raw["listing_snapshots"] = [
        {
            "product_ref": "1",
            "external_id": "peer-50ml",
            "market": "amazon",
            "price": p,
            "mrp": 100,
            "url": "https://source.test/peer-50ml",
            "captured_at": day,
        }
        for day, p in [("2026-10-22", 90), ("2026-11-21", 79)]
    ]
    trends = {
        "launches": [
            launch,
            dict(launch, date="2025-11-01", brand="B"),
            dict(launch, category="Serum", brand="C"),
        ]
    }
    claims = build_swot(raw, m, {}, trends, AS_OF)["threat"]
    assert {r["rule"] for r in claims} == {
        "brand_momentum",
        "recent_launch",
        "discount_pressure",
    }
    claim = next(r for r in claims if r["rule"] == "recent_launch")
    assert claim["n"] == 1 and claim["title"].endswith("catalog launch")


def test_negative_aspect_needs_separation_and_reported_complaint_examples():
    raw, m = _cohort()
    a = m["brands"]["Dot & Key"]["aspects"]["hydration"]
    a.update(
        nss=-0.8,
        wilson=[0.03, 0.22],
        complaint_lift=2.2,
        low_rating_mentions=7,
        low_rating_count=9,
        low_rating_evidence=[{"quote": "Still dry", "rating": 1}],
    )
    weak = build_swot(raw, m, {}, {}, AS_OF)["weakness"]
    assert {r["rule"] for r in weak} == {"aspect_disadvantage", "complaint_lift"}
    assert (
        next(r for r in weak if r["rule"] == "complaint_lift")["evidence_quotes"][0][
            "rating"
        ]
        == 1
    )


def test_marketplace_discount_uses_one_listing_and_exact_boundary_dates():
    raw, metrics = _cohort()
    metrics["products"]["1"]["price"]["discount_change_30d"] = 0.99

    def snapshot(market, external_id, day, price, url):
        return {
            "product_ref": "1",
            "market": market,
            "external_id": external_id,
            "captured_at": day,
            "price": price,
            "mrp": 100,
            "url": url,
        }

    raw["listing_snapshots"] = [
        snapshot("amazon", "small", "2026-10-22T09:00:00Z", 90, "https://old/small"),
        snapshot("amazon", "small", "2026-11-21T20:00:00Z", 80, "https://new/small"),
        snapshot(
            "amazon", "small", "2026-11-21T05:00:00Z", 81, "https://earlier/small"
        ),
        snapshot("amazon", "other", "2026-10-22", 100, "https://other"),
        snapshot("flipkart", "other", "2026-11-21", 10, "https://other-fk"),
        snapshot("amazon", "near", "2026-10-23", 100, "https://nearby"),
        snapshot("amazon", "near", "2026-11-21", 70, "https://nearby"),
        snapshot("flipkart", "below", "2026-10-22", 90, "https://below"),
        snapshot("flipkart", "below", "2026-11-21", 80.01, "https://below"),
    ]
    rules = build_swot(raw, metrics, {}, {}, AS_OF)["threat"]
    (row,) = rules
    assert row["rule"] == "discount_pressure" and row["n"] == 2
    assert row["evidence_sources"] == ["https://new/small", "https://old/small"]
    values = row["metric_values"]
    assert (values["market"], values["external_id"]) == ("amazon", "small")
    assert (values["from_date"], values["to_date"]) == ("2026-10-22", "2026-11-21")
    assert values["discount_change_30d"] == 0.10 and values["before"]["price"] == 90
    assert values["after"]["captured_at"] == "2026-11-21T20:00:00Z"


def test_momentum_selects_latest_timestamp_and_reads_fractional_traffic_growth():
    raw, metrics = _cohort()

    def signal(brand, when, ratio):
        return {
            "brand": brand,
            "source": "crustdata_company",
            "domain": "example.test",
            "captured_at": when,
            "web_traffic": {"quarterly_growth": ratio},
            "source_url": "https://provider.test/evidence",
        }

    raw["brand_signals"] = [
        signal("A", "2026-11-20T23:00:00Z", 0.20),
        signal(
            "A", "2026-11-21T01:00:00+05:30", 0.10
        ),  # Earlier instant despite local date.
        signal("A", "2026-11-22T02:00:00Z", 0.8),
        signal("B", "2026-11-21T12:00:00Z", 0.19),
        signal("B", "2026-11-18T12:00:00Z", 0.40),
    ]
    (row,) = build_swot(raw, metrics, {}, {}, AS_OF)["threat"]
    assert row["subject"] == "A/traffic" and row["metric_values"]["qoq_percent"] == 20
    assert row["metric_values"]["observed_at"] == "2026-11-20T23:00:00Z"
    assert row["evidence_sources"] == ["https://provider.test/evidence"]


def test_live_company_traffic_uses_brand_domain_and_excludes_parent_or_external_market():
    raw, metrics = _cohort()
    raw["brand_signals"] = [
        {
            "brand": brand,
            "source": "crustdata_company",
            "entity_scope": scope,
            "domain": "www.brand.test",
            "captured_at": "2026-11-17",
            "web_traffic": {
                "domain_traffic": {
                    "brand.test": {"qoq_pct": 25},
                    "other.test": {"qoq_pct": 75},
                }
            },
        }
        for brand, scope in [("A", "brand"), ("B", "parent_company"), ("C", "us_brand")]
    ]
    (row,) = build_swot(raw, metrics, {}, {}, AS_OF)["threat"]
    assert row["subject"] == "A/traffic" and row["metric_values"]["qoq_percent"] == 25
