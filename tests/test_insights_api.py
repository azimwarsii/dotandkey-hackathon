"""Exercise the offline Part 2 endpoints and CLI against a small real SQLite store."""

from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from market_intel.api import app
from market_intel.store import Store


@pytest.fixture
def insight_data(tmp_path, monkeypatch):
    db_path = tmp_path / "part1.sqlite3"
    catalog_path = tmp_path / "absent-history.sqlite3"
    monkeypatch.setenv("MARKET_INTEL_DB", str(db_path))
    monkeypatch.setenv("COMPETITOR_CATALOG_DB", str(catalog_path))
    with closing(Store(db_path)) as store:
        product = {"product_ref": "s1", "title": "Gel Sunscreen", "category": "Sunscreen",
                   "brand": "Dot & Key", "size": "50 ml", "published_at": "2026-01-31"}
        store.save_product(product)
        listing = {"product_ref": "s1", "market": "amazon", "external_id": "SKU01",
                   "url": "https://example.org/sunscreen", "size": "50 ml"}
        store.save_listing(listing, {"captured_at": "2026-02-02T01:00:00+05:30", "price": 250,
                                     "mrp": 300, "rating": 4.0, "rating_count": 100})
        store.save_listing(listing, {"captured_at": "2026-02-02T08:00:00Z", "price": 150,
                                     "mrp": 300, "rating": 4.5, "rating_count": 120})
        store.save_reviews([
            {"product_ref": "s1", "date": "2026-02-02T01:00:00+05:30", "body": "Feels lightweight.",
             "rating": 5, "source": "amazon", "url": listing["url"]},
            {"product_ref": "s1", "date": "2026-02-02T08:00:00Z", "body": "Too greasy.",
             "rating": 2, "source": "amazon", "url": listing["url"]},
            {"product_ref": "s1", "date": "2026-01-31", "observed_at": "2026-02-02T08:00:00Z",
             "body": "I like the fragrance.", "rating": 4, "source": "amazon", "url": listing["url"]},
        ])
    return db_path, catalog_path


def _cli_output(command, tmp_path):
    output = tmp_path / f"{command[0]}.json"
    subprocess.run([sys.executable, "-m", "market_intel", *command, "--as-of", "2026-02-01",
                    "--output", str(output)], check=True, cwd=Path(__file__).resolve().parents[1],
                   env=os.environ.copy(), capture_output=True, text=True)
    return json.loads(output.read_text())


def test_category_insights_http_and_cli_match_at_utc_cutoff(insight_data, tmp_path):
    _, catalog_path = insight_data
    with TestClient(app) as client:
        response = client.get("/category/sunscreen/insights", params={"as_of": "2026-02-01"})
        assert response.status_code == 200
        report = response.json()
        latest = client.get("/category/Sunscreen/insights").json()
        assert client.get("/category/not-a-category/insights").status_code == 404
        assert client.get("/category/Sunscreen/insights?as_of=garbage").status_code == 422
    assert report == _cli_output(["insights", "Sunscreen"], tmp_path)
    assert report["as_of"] == "2026-02-01"
    stats = report["metrics"]["products"]["s1"]
    assert report["scope"]["review_count"] == stats["review_count"] == 1
    assert stats["rating"]["n"] == 100 and stats["rating"]["mean"] == 4.0
    assert stats["aspects"]["greasy_sticky"]["pos"] == 1
    assert stats["price"]["by_unit"]["ml"]["median_per_unit"] == 5.0
    assert stats["velocity"]["per_day"] is None
    assert latest["as_of"] == "2026-02-02"
    assert latest["metrics"]["products"]["s1"]["review_count"] == 3
    assert latest["metrics"]["products"]["s1"]["velocity"]["per_day"] == 20.0
    coverage = report["scope"]["catalog_snapshot_coverage"]
    assert coverage and all(row["status"] == "no_snapshot" for row in coverage)
    assert not report["trends"]["launches"]
    assert report["forecast"]["status"] == "insufficient_history"
    assert report["forecast"]["opportunity_score"] is None
    assert not catalog_path.exists()


def test_opportunity_overview_keeps_category_with_missing_history(insight_data, tmp_path):
    with TestClient(app) as client:
        response = client.get("/insights/opportunities", params={"as_of": "2026-02-01"})
        assert response.status_code == 200
    overview = response.json()
    assert overview == _cli_output(["opportunities"], tmp_path)
    row, = overview["categories"]
    assert (row["category"], row["as_of"]) == ("Sunscreen", "2026-02-01")
    assert row["insights_path"] == "/category/Sunscreen/insights"
    assert row["opportunity_score"] is None and row["reason"]
    assert row["recent_catalog_launches"] == 0


def test_catalog_only_category_resolves_default_date_without_snapshots(insight_data):
    db_path, _ = insight_data
    with closing(Store(db_path)) as store:
        store.save_product({"product_ref": "t1", "title": "Rice Toner", "category": "Toner", "brand": "Dot & Key",
                            "published_at": "2026-02-03T01:00:00+05:30"})
    with TestClient(app) as client:
        response = client.get("/category/Toner/insights")
    assert response.status_code == 200
    report = response.json()
    assert report["as_of"] == "2026-02-02"
    stats = report["metrics"]["products"]["t1"]
    assert stats["review_count"] == stats["rating"]["n"] == 0
    assert stats["rating"]["bayesian"] is None and stats["price"]["by_unit"] == {}
    assert stats["velocity"]["per_day"] is None and report["forecast"]["projection"] == []
