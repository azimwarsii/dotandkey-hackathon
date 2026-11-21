"""Read and write API contracts exercised against a small persistent store."""

import json
import os
import time
from contextlib import closing
from datetime import date
from threading import Event

import pytest
from fastapi.testclient import TestClient

from market_intel.api import app
from market_intel.frontend_api import cache, jobs
from market_intel.frontend_api.evidence import resolve_evidence
from market_intel.store import Store
from market_intel.studio import runs


@pytest.fixture
def market(tmp_path, monkeypatch):
    db = tmp_path / "market.sqlite3"
    for key, value in {
        "MARKET_INTEL_DB": db,
        "COMPETITOR_CATALOG_DB": tmp_path / "absent.sqlite3",
        "MARKET_INSIGHT_CACHE": tmp_path / "cache/insights",
        "STUDIO_RUNS_DIR": tmp_path / "studio/runs",
    }.items():
        monkeypatch.setenv(key, str(value))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    p = {
        "product_ref": "dk:1",
        "handle": "test-spf",
        "title": "Gel SPF 50",
        "category": "Sunscreen",
        "brand": "Dot & Key",
        "price": 399,
        "images": ["https://example.com/gel.png"],
        "published_at": "2026-01-01",
        "is_combo": False,
    }
    listing = {
        "product_ref": "dk:1",
        "market": "amazon",
        "url": "https://example.com/gel",
        "external_id": "A1",
    }
    with closing(Store(db)) as store:
        store.save_product(p)
        store.save_listing(
            listing,
            {
                "captured_at": "2026-02-03",
                "price": 350,
                "rating": 4.5,
                "rating_count": 210,
            },
        )
        store.save_listing(
            listing,
            {
                "captured_at": "2026-03-03",
                "price": 330,
                "rating": 4.3,
                "rating_count": 230,
            },
        )
        store.save_reviews(
            [
                {
                    "product_ref": "dk:1",
                    "date": "2026-02-05",
                    "rating": 5,
                    "body": "Absorbs quickly.",
                    "source": "amazon",
                },
                {
                    "product_ref": "dk:1",
                    "date": "2026-02-15",
                    "observed_at": "2026-03-03",
                    "rating": 1,
                    "body": "Too greasy.",
                    "source": "amazon",
                },
            ]
        )
    with TestClient(app) as client:
        yield client, db


def messages(response):
    return [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def test_catalog_historical_detail_and_scope(market):
    c, _ = market
    assert (
        c.get("/api/products?category=sunscreen&q=gel").json()["products"][0]["handle"]
        == "test-spf"
    )
    assert c.get("/api/products?as_of=2025-12-31").json()["products"] == []
    data = c.get("/api/products/test-spf?as_of=2026-02-20").json()
    assert data["listings"][0]["price"] == 350
    assert len(data["snapshots"]) == len(data["reviews"]) == 1
    assert c.get("/api/products/test-spf?as_of=2025-12-31").status_code == 404
    assert c.get("/api/competitors?category=unknown").status_code == 404
    assert c.get("/api/launches").json()["launches"] == []
    assert c.get("/api/health").json()["status"] == "ok"


def test_cached_overview_cutoffs_and_invalidation(market, monkeypatch):
    c, db = market
    url = "/api/overview?category=sunscreen&as_of=2026-02-20&compare=2026-02-01"
    response = c.get(url).json()
    assert response["category"] == "Sunscreen"
    assert sum(r["positive"] for r in response["review_velocity"]) == 1
    assert sum(r["negative"] for r in response["review_velocity"]) == 0
    assert response["review_share"]["markets"][0]["rating"] == 4.5
    assert response["categories"][0]["opportunity_score"] is None
    assert c.get("/api/overview?as_of=2026-02-02&compare=2026-03-03").status_code == 422
    assert (cache.directory() / "sunscreen-2026-02-20.json").is_file()
    build = cache.build_insights
    monkeypatch.setattr(
        cache, "build_insights", lambda *a: pytest.fail("warm cache rebuilt")
    )
    assert (
        c.get("/api/category/sunscreen/insights?as_of=2026-02-20").json()["metrics"][
            "category"
        ]["review_count"]
        == 1
    )
    assert c.get(url).json() == response
    monkeypatch.setattr(cache, "build_insights", build)
    with closing(Store(db)) as store:
        store.save_reviews(
            [
                {
                    "product_ref": "dk:1",
                    "date": "2026-02-08",
                    "rating": 2,
                    "body": "Sticky finish.",
                    "source": "amazon",
                }
            ]
        )
        # Exercise WAL visibility while the writer's connection is still open.
        assert sum(r["negative"] for r in c.get(url).json()["review_velocity"]) == 1


def test_question_citations_resolve_from_server_data(market):
    c, _ = market
    result = c.post(
        "/api/ask",
        json={"category": "Sunscreen", "question": "What is the demand forecast?"},
    )
    assert result.headers["content-type"].startswith("text/event-stream")
    frames = messages(result)
    assert [f["type"] for f in frames] == ["token", "citations", "done"]
    (citation,) = frames[1]["citations"]
    evidence = resolve_evidence("Sunscreen", date(2026, 3, 3), citation["id"])
    assert citation["title"] == evidence["title"]
    assert citation["href"].endswith("#forecast")
    assert resolve_evidence("Sunscreen", None, "invented-id") is None
    assert (
        messages(c.post("/api/ask", json={"question": "popcorn unicorns"}))[1][
            "citations"
        ]
        == []
    )


def test_job_dedup_progress_and_studio_compatibility(market, monkeypatch):
    c, _ = market
    started, finish = Event(), Event()

    def harvest(kind, category, progress):
        progress("Refreshing catalog")
        started.set()
        assert finish.wait(8)

    monkeypatch.setattr(jobs, "collect", harvest)
    job = c.post("/api/refresh?category=sunscreen").json()
    try:
        assert started.wait(2)
        assert c.get("/api/jobs/" + job["id"]).json()["stage"] == "Refreshing catalog"
        assert c.post("/api/refresh").json()["id"] == job["id"]
        assert c.post("/api/jobs/nightly").status_code == 403
        monkeypatch.setenv("JOBS_CRON_TOKEN", "test-credential")
        assert (
            c.post(
                "/api/jobs/nightly", headers={"Authorization": "Bearer wrong"}
            ).status_code
            == 403
        )
        assert (
            c.post(
                "/api/jobs/nightly", headers={"Authorization": "Bearer test-credential"}
            ).status_code
            == 409
        )
    finally:
        finish.set()
    assert (
        messages(c.get("/api/jobs/" + job["id"] + "/events"))[-1]["status"]
        == "complete"
    )
    folder = runs.run_path("example")
    folder.mkdir(parents=True)
    studio = runs.submit(folder, "Generate campaign", lambda: None)
    assert (
        messages(c.get("/api/jobs/" + studio["id"] + "/events"))[-1]["status"]
        == "complete"
    )
    assert c.get("/api/jobs/no-such-job/events").status_code == 404


def test_pruning_preserves_pinned_recent_and_active_runs(market):
    old = time.time() - 16 * 86400
    for name in ("old", runs.DEMO, "pinned", "active", "recent-job"):
        path = runs.run_path(name)
        runs.write_json(path / "run.json", {"id": name, "pinned": name == "pinned"})
        os.utime(path / "run.json", (old, old))
    runs.write_json(
        runs.run_path("recent-job") / "jobs/last.json", {"status": "complete"}
    )
    with runs.locked(runs.run_path("active")):
        jobs.prune_old_runs()
    assert {p.name for p in runs.root().iterdir()} == {
        runs.DEMO,
        "pinned",
        "active",
        "recent-job",
    }


def test_real_studio_brief_route_emits_ordered_resumable_stages(market, monkeypatch):
    import market_intel.studio_creative as creative

    c, _ = market
    dir_ = runs.run_path("staged")
    runs.write_json(dir_ / "run.json", {"handle": "test-spf"})
    started, finish = Event(), Event()

    def brief(*args):
        started.set()
        assert finish.wait(5)
        return {"product": {"handle": "test-spf"}}

    monkeypatch.setattr(creative, "build_brief", brief)
    job = c.post("/studio/runs/staged/brief").json()
    base = "/api/jobs/" + job["id"]
    try:
        assert started.wait(1)
        assert c.get(base).json()["stage"] == "Fetching catalog and insight evidence"
    finally:
        finish.set()
    events = messages(c.get(base + "/events"))
    assert [r["stage"] for r in events] == [
        "Preparing product brief",
        "Fetching catalog and insight evidence",
        "Assembling product brief",
        "Complete",
    ]
    assert events[-1]["status"] == "complete"
    assert (
        messages(c.get(base + "/events", headers={"Last-Event-ID": "3"})) == events[-1:]
    )


def test_public_historical_cache_stays_bounded(market, monkeypatch):
    c, _ = market
    monkeypatch.setattr(cache, "MAX_CATEGORY_DATES", 4)
    current = c.get("/api/overview").json()
    for day in (2, 3, 4, 5, 6, 7):
        assert (
            c.get(
                f"/api/category/Sunscreen/insights?as_of=2026-02-{day:02}"
            ).status_code
            == 200
        )
    assert len(list(cache.directory().glob("sunscreen-*.index.json"))) == 4
    assert len(list(cache.directory().glob("sunscreen-*.json"))) == 8
    for day in (current["as_of"], current["compare"]):
        assert (cache.directory() / f"sunscreen-{day}.json").is_file()


def test_refresh_honors_deadline_for_rate_limit_wait(tmp_path):
    import httpx

    from market_intel.client import Client

    endpoint = httpx.MockTransport(
        lambda request: httpx.Response(429, headers={"retry-after": "3600"})
    )
    with (
        closing(
            Client(
                tmp_path / "cache",
                lambda *a, **kw: None,
                transport=endpoint,
                deadline=time.monotonic() + 30,
            )
        ) as http,
        pytest.raises(TimeoutError, match="time limit"),
    ):
        http.get("https://example.test/source")
