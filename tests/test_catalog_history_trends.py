from datetime import date
import json
import sqlite3

from market_intel import catalog_history as history
from market_intel.client import SourceUnavailable
from market_intel.trends import build_trends, find_terms


class Storefront:
    def __init__(self, products, *, fail=False, currency="INR"):
        self.products, self.fail, self.currency = products, fail, currency
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        if url.endswith("/cart.js"):
            return json.dumps({"currency": self.currency})
        if self.fail and params["page"] == 2:
            raise SourceUnavailable("HTTP 503")
        return json.dumps({"products": self.products if params["page"] == 1 else []})


def product(id_, created, title, price=450, mrp=500):
    return {"id": id_, "handle": str(id_), "title": title, "created_at": created, "published_at": "2026-11-20",
            "product_type": "", "tags": [], "variants": [{"id": id_ * 10, "price": str(price),
            "compare_at_price": str(mrp), "title": "50g", "available": True}]}


def test_atomic_run_then_daily_snapshot_and_price_comparison(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "BRANDS", ["Foxtale"])
    path = tmp_path / "catalog.sqlite3"
    original = product(5, "2026-10-01", "Centella daily SPF 50 sunscreen")
    baseline = [original, product(2, "2022-01-01", "Niacinamide SPF 50 sunscreen"),
                product(3, "2026-10-01", "Combo of three sunscreens"),
                product(4, "2026-10-01", "Niacinamide SPF 50 sunscreen")]
    first = date(2026, 10, 22)
    assert history.snapshot_catalogs(Storefront(baseline, fail=True), path, first)["errors"]
    assert history.latest_snapshot_date(path) is None
    good = Storefront(baseline)
    assert history.snapshot_catalogs(good, path, first)["brands"] == {"Foxtale": 4}
    calls = len(good.calls)
    history.snapshot_catalogs(good, path, first)
    assert len(good.calls) == calls
    ctx = history.catalog_context(path, "sunscreen", first)
    assert [r["title"] for r in ctx["launches"]] == [original["title"]]
    assert len(ctx["products"]) == 2 and len(ctx["historical_products"]) == 2
    assert not ctx["price_changes"] and ctx["coverage"][0]["currency"] == "INR"

    second = date(2026, 11, 21)
    later = [product(5, "2026-10-01", original["title"], price=350),
             product(9, "2024-05-01", "Vitamin E broad spectrum sunscreen")]
    history.snapshot_catalogs(Storefront(later), path, second)
    ctx = history.catalog_context(path, "Sunscreen", second)
    event = next(e for e in ctx["launches"] if e["title"].startswith("Vitamin E"))
    assert event["launch_basis"] == "first_seen_after_baseline" and event["date"] == str(second)
    assert len(ctx["products"]) == 2 and len(ctx["historical_products"]) == 3
    assert round(ctx["price_changes"][0]["discount_change_30d"], 3) == 0.2
    assert len(history.catalog_context(path, "Sunscreen", first)["products"]) == 2


def test_reclassification_is_not_a_second_launch_and_foreign_currency_is_retained(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "BRANDS", ["Foxtale"])
    path = tmp_path / "history.db"
    history.snapshot_catalogs(Storefront([product(1, "2026-11-09", "Ceramide face serum")], currency="USD"),
                              path, date(2026, 11, 10))
    history.snapshot_catalogs(Storefront([product(1, "2026-11-09", "Ceramide face cleanser")], currency="USD"),
                              path, date(2026, 11, 11))
    ctx = history.catalog_context(path, "Face Wash", date(2026, 11, 11))
    assert not ctx["launches"] and ctx["products"][0]["currency"] == "USD"
    original = history.catalog_context(path, "Serum", date(2026, 11, 11))
    assert len(original["launches"]) == 1 and original["products"] == []


def test_prior_to_baseline_and_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "BRANDS", ["Foxtale"])
    path = tmp_path / "missing.db"
    assert history.latest_snapshot_date(path) is None
    assert history.catalog_context(path, "Serum", date.today())["coverage"][0]["status"] == "no_snapshot"
    assert not path.exists()


def test_trending_requires_two_supported_signals_and_preserves_sources():
    def launch(i, day, title):
        return dict(product_ref=f"shop:{i}", created_at=day, title=title, url=f"https://shop.test/{i}")
    rows, reviews = [], []
    for i in range(30):
        for recent, created, reviewed in [(False, "2025-09-01", "2026-03-05"), (True, "2026-10-12", "2026-10-18")]:
            title = "Bakuchiol" if recent and i < 20 else "Moisturiser"
            rows.append(launch((recent, i), created, title))
            reviews.append({"body": f"{title} skincare review {i}", "date": reviewed,
                            "source_url": f"https://reviews.test/{i}", "source": "judgeme"})
    raw = {"category": "Moisturiser", "reviews": reviews,
           "products": [{"brand": "Dot & Key", "title": "Daily cream"}]}
    context = {"historical_products": rows}
    trends = build_trends(raw, context, date(2026, 11, 21))
    term, = trends["trending"]
    assert term["term"] == "bakuchiol" and term["missing_at_dot_key"] and term["growth"] >= 1.5
    assert term["n"] == 40 and term["signals"]["review_mentions"]["recent_n"] == 30
    assert term["signals"]["review_mentions"]["recent_examples"][0]["url"].startswith("https://reviews.test/")
    assert not build_trends({**raw, "reviews": []}, context, date(2026, 11, 21))["trending"]
    assert {"centella", "fragrance free"} <= find_terms("Cica, fragrance-free soothing lotion")


def test_corroboration_only_uses_a_matching_product():
    event = {"brand": "Foxtale", "title": "Barrier Repair Ceramide Cream", "date": "2026-11-10"}
    raw = {"products": [{"brand": "Foxtale", "title": "Barrier Repair Ceramide Face Cream", "product_ref": "x"},
                        {"brand": "Foxtale", "title": "Vitamin C Face Cream", "product_ref": "y"}],
           "reviews": [{"product_ref": "x", "date": "2026-11-01", "source_url": "https://shop/review/1"},
                       {"product_ref": "y", "date": "2020-01-01"}],
           "news_items": [{"brand": "Foxtale", "title": "Foxtale unveils barrier repair ceramide cream",
                           "date": "2026-11-12","url":"https://news/test"}]}
    ctx = {"launches": [event], "as_of": "2026-11-21"}
    checks = history.corroborate_launches(raw, ctx)[0]["crosschecks"]
    assert [r["type"] for r in checks] == ["earliest_observed_review", "matching_launch_news"]
    assert checks[0]["predates_launch_signal"] and checks[0]["url"] == "https://shop/review/1"


def test_new_asin_needs_two_real_pages_and_is_category_specific(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "BRANDS", ["Foxtale"])
    path = tmp_path / "catalog.db"
    history.snapshot_catalogs(Storefront([product(1, "2026-10-01", "Centella sunscreen")]), path, date(2026, 11, 20))
    first = {"external_id": "B000000001", "title": "Centella Sunscreen"}
    new = {"external_id": "B000000002", "title": "Barrier SPF 50 Sunscreen"}
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE amazon_search(day TEXT,category TEXT,source_url TEXT,results TEXT)")
        for day, rows in [("2026-11-19",[first]),("2026-11-21",[first,new])]:
            db.execute("INSERT INTO amazon_search VALUES(?,?,?,?)", (day,"Sunscreen","https://amazon.in/s?k=sunscreen",json.dumps(rows)))
    assert not history.catalog_context(path,"Sunscreen",date(2026,11,20))["asin_changes"]
    changes = history.catalog_context(path,"Sunscreen",date(2026,11,21))["asin_changes"]
    assert len(changes) == 1 and changes[0]["external_id"] == new["external_id"]
