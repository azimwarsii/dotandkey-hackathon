from datetime import date
import json

import pytest

from market_intel.aspects import tag_sentence
from market_intel.metrics import build_metrics, utc_date
from validation.evaluate_aspects import evaluate, REPORT


def test_tagger_scopes_and_overlaps():
    assert tag_sentence("No white cast but a greasy finish") == {"white_cast": "pos", "greasy_sticky": "neg"}
    assert tag_sentence("Not greasy, but sticky.") == {"greasy_sticky": "mixed"}
    assert tag_sentence("The scent.", 3) == {"fragrance": "neutral"}
    assert tag_sentence("The scent.", 2) == {"fragrance": "neg"}


def test_validation_is_reproducible_and_gates_sparse_aspects():
    report = evaluate()
    assert report == json.loads(REPORT.read_text())
    assert report["sentences"] == 150
    assert report["aspects"]["white_cast"]["enabled"] is False
    assert report["aspects"]["authenticity"]["enabled"] is False


def test_metrics_counts_scopes_history_and_units():
    rows = [{"product_ref": "a", "brand": "Dot & Key", "size": "20 g"},
            {"product_ref": "b", "brand": "Peer", "size": "10 g"},
            {"product_ref": "c", "brand": "Peer", "size": "10 ml"}]
    listings = [{"product_ref": p["product_ref"], "external_id": p["product_ref"], "size": p["size"],
                 "market": "amazon", "url": "https://example.in/"+p["product_ref"]} for p in rows]
    def snapshot(i, day, price, n, rating):
        return {**listings[i], "price": price, "mrp": 200, "rating_count": n, "rating": rating,
                "captured_at": f"2026-{day}T00:00:00+00:00"}
    history = [snapshot(0, "10-22", 200, 50, 1), snapshot(0, "11-21", 100, 80, 3),
               snapshot(1, "11-20", 100, 22, 4), snapshot(1, "11-21", 100, 20, 5),
               snapshot(2, "11-21", 30, 0, None), snapshot(2, "11-22", 50, 1000, 4)]
    reviews = [{"product_ref": "a", "body": f"Review {i}. Non greasy. Lightweight.", "date": "2026-11-20",
                "rating": 4, "source": "amazon"} for i in range(29)]
    reviews += [{"product_ref": "a", "body": "It is greasy.", "date": "2026-11-20", "rating": 1, "source": "amazon"},
                {"product_ref": "a", "body": "Nice.", "date": "2026-11-20", "rating": 2, "source": "amazon"},
                {"product_ref": "b", "body": "Greasy.", "date": "2026-11-22", "rating": 1, "source": "amazon"},
                {"product_ref": "b", "body": "Undated", "source": "amazon"},
                {"product_ref": "b", "body": "Recent undated", "observed_at":"2026-11-20", "source": "amazon"}]
    metrics = build_metrics(dict(products=rows, listings=listings, listing_snapshots=history, reviews=reviews),
                            date(2026, 11, 21))
    a = metrics["products"]["a"]
    assert metrics["category"]["rating"]["n"] == 100
    assert a["rating"]["prior_mean"] == 3.4
    assert a["rating"]["bayesian"] == pytest.approx((50*3.4+80*3)/130)
    assert a["price"]["by_unit"]["g"]["index"] == pytest.approx(5/7.5)
    assert metrics["products"]["c"]["price"]["by_unit"]["ml"]["index"] == 1
    assert a["price"]["discount_change_30d"] == .5
    assert a["velocity"]["per_day"] == 1
    assert metrics["products"]["b"]["velocity"]["per_day"] is None
    assert metrics["products"]["b"]["velocity"]["undated_reviews"] == 1
    assert metrics["excluded_reviews"] == {"after_cutoff": 1, "unknown_date_and_observation": 1}
    aspect = a["aspects"]["greasy_sticky"]
    assert aspect["directional_n"] == 30 and aspect["mentions"] == 30
    assert aspect["mention_rate"] == pytest.approx(30/31)
    assert aspect["nss"] == pytest.approx(28/30)
    assert aspect["complaint_lift"] == pytest.approx((1/2)/(30/31))
    assert 0 < aspect["wilson"][0] < 29/30 < aspect["wilson"][1] < 1
    assert aspect["claim_eligible"]
    assert utc_date("2026-11-22T01:00:00+05:30") == date(2026, 11, 21)


def test_pack_and_missing_size_do_not_fabricate_price_index():
    products = [{"product_ref":"A","brand":"Brand","title":"Pack","size":"10 ml","variants":[
        {"sku":"small","size":"10 ml"},{"sku":"large","size":"20 ml"}]}]
    listings = [{"product_ref":"A","external_id":"one","market":"amazon","title":"Pack of 2","size":"10ml"},
                {"product_ref":"A","external_id":"ambiguous","market":"flipkart","title":"Single"}]
    observations = [dict(l, captured_at="2026-01-01",price=20) for l in listings]
    metric = build_metrics(dict(products=products,listings=listings,listing_snapshots=observations), date(2026,1,1))
    assert metric["category"]["price"]["n"] == 2
    assert metric["category"]["price"]["by_unit"] == {}


def test_variant_rating_groups_separate_sizes_and_require_unambiguous_shade():
    product = {"product_ref":"p","brand":"Example","size":"50 ml","variants":[
        {"sku":"small","size":"50 ml"},{"sku":"large-pink","size":"80 ml"},{"sku":"large-red","size":"80 ml"}]}
    listings = [
        {"external_id":"small-amazon","market":"amazon","size":"50ml"},
        {"external_id":"small-flipkart","market":"flipkart","matched_variant_sku":"small"},
        {"external_id":"unknown-shade","market":"nykaa","size":"80ml"},
        {"external_id":"large","market":"flipkart","matched_variant_sku":"large-red"},
        {"external_id":"inconsistent","market":"nykaa","matched_variant_sku":"large-pink","size":"50ml"},
    ]
    for l in listings:
        l.update(product_ref="p",url="https://example.in/"+l["external_id"])
    series = [dict(l,rating=4.5,rating_count=110,captured_at="2026-01-02") for l in listings]
    review = {"product_ref": "p", "body":"Feels greasy.", "rating":2,"source":"amazon","date":"2026-01-01"}
    result = build_metrics(dict(products=[product], reviews=[review], listing_snapshots=series, listings=listings),
                           date(2026, 1, 2))["products"]["p"]
    by_variant = result["rating"]["by_variant"]
    assert set(by_variant) == {"small", "large-red"}
    assert set(by_variant["small"]) == {"flipkart","amazon"}
    assert by_variant["small"]["amazon"] == {"mean":4.5,"n":110,"urls":["https://example.in/small-amazon"]}
    assert result["aspects"]["greasy_sticky"]["low_rating_evidence"][0]["quote"] == "Feels greasy."


def test_parent_rating_counts_stay_out_of_variant_metrics_but_child_prices_remain():
    from datetime import date
    from market_intel.metrics import build_metrics

    product = {"product_ref": "p", "brand": "Dot & Key", "title": "Gel",
               "variants": [{"sku": "sku50", "size": "50 g"}]}
    listing = {"product_ref": "p", "external_id": "child", "market": "nykaa",
               "matched_variant_sku": "sku50", "url": "https://example.test/p"}
    snap = {**listing, "rating_scope": "parent_product", "rating_scope_id": "parent",
            "price_scope": "selected_variant", "rating": 4.5, "rating_count": 9000,
            "price": 300, "captured_at": "2026-11-21"}
    report = {"category": "Sunscreen", "products": [product], "listings": [listing],
              "listing_snapshots": [snap], "reviews": []}
    stats = build_metrics(report, date(2026, 11, 21))["products"]["p"]
    assert stats["rating"]["n"] == 0 and not stats["rating"]["by_variant"]
    assert stats["price"]["by_unit"]["g"]["median_per_unit"] == 6
