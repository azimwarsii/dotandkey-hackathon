import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from market_intel.api import app
from market_intel.studio import runs


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_RUNS_DIR", str(tmp_path / "runs"))
    folder = runs.run_path("example")
    folder.mkdir(parents=True)
    runs.write_json(folder / "run.json", {"id": "example", "handle": "watermelon"})
    runs.write_json(
        folder / "brief.json", {"product": {"handle": "watermelon", "local_images": []}}
    )
    return TestClient(app), folder


def finished(client):
    for _ in range(100):
        state = client.get("/studio/runs/example").json()
        if state["jobs"][0]["status"] != "running":
            return state
        time.sleep(0.025)
    pytest.fail("Studio operation did not finish")


def test_local_translation_route_and_origin(studio, monkeypatch):
    from market_intel.studio_creative import localize

    client, folder = studio
    base = "/studio/runs/example/localize"
    runs.write_json(folder / "creative.json", {"script": {"id": "script"}})

    def translate(dest, brief, creative, language):
        assert creative["script"]["id"] == "script"
        runs.write_json(dest / "locales" / (language + ".json"), {"language": language})

    monkeypatch.setattr(localize, "localize", translate)
    assert client.post(base, json={"language": "fr"}).status_code == 422
    body = {"language": "hi-IN"}
    assert (
        client.post(
            base, json=body, headers={"origin": "https://example.org"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            base, json=body, headers={"origin": "http://127.0.0.1:3000"}
        ).status_code
        == 202
    )
    assert finished(client)["locales"]["hi-IN"]["language"] == "hi-IN"


def test_studio_upload_blocked_links_and_ad_dates(studio, monkeypatch):
    import market_intel.studio_research as research

    client, _folder = studio

    def analyze(root, *, url=None, paths=None, **kw):
        assert paths[0].read_bytes() == b"attachment"
        post = {"id": "verified-ad", "status": "ready", "frames": [], "url": url}
        runs.write_json(root / "research/verified-ad/post.json", post)
        return post

    monkeypatch.setattr(research, "deconstruct", analyze)
    base = "/studio/runs/example"
    assert (
        client.post(base + "/uploads?filename=test.html", content=b"text").status_code
        == 415
    )
    key = client.post(base + "/uploads?filename=ad.png", content=b"attachment").json()[
        "id"
    ]
    assert (
        client.post(
            base + "/deconstruct", json={"url": "https://not-a-platform.example/a"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base + "/deconstruct", json={"uploads": ["../secret.png"]}
        ).status_code
        == 404
    )
    reply = client.post(
        base + "/deconstruct",
        json={
            "url": "https://www.facebook.com/ads/library/?id=123",
            "uploads": [key],
            "ad_start": "2026-01-01",
            "ad_end": "2026-02-05",
        },
    )
    assert reply.status_code == 202
    result = finished(client)
    assert result["jobs"][0]["status"] == "complete"
    assert result["posts"][0]["ad_lifetime"]["observed_days_running"] >= 30
    assert client.get(base + "/assets/run.json").is_success
    assert client.get(base + "/assets/.lock").status_code == 404


def test_studio_campaign_versions_and_job_lock(studio, monkeypatch):
    import market_intel.studio_creative as creative

    client, folder = studio
    runs.write_json(folder / "concepts.json", [{"id": "idea"}])
    (folder / "inputs").mkdir()
    (folder / "inputs/photo.png").write_bytes(b"product image")
    runs.write_json(
        folder / "brief.json", {"product": {"local_images": ["inputs/photo.png"]}}
    )

    def generate(dest, brief, patterns, concept, reference=None):
        assert (dest / "inputs/photo.png").read_bytes() == b"product image"
        return {"script": {"id": "draft"}, "variants": [{"id": "variant"}]}

    monkeypatch.setattr(creative, "generate", generate)
    base = "/studio/runs/example"
    assert (
        client.post(base + "/generate", json={"concept_id": "unknown"}).status_code
        == 404
    )
    with runs.locked(folder):
        assert (
            client.post(base + "/generate", json={"concept_id": "idea"}).status_code
            == 409
        )
    assert (
        client.post(base + "/generate", json={"concept_id": "idea"}).status_code == 202
    )
    state = finished(client)
    assert state["creative"]["script"]["id"] == "draft"
    assert Path(state["selected"]["directory"]).parts[0] == "campaigns"
    from market_intel import studio_film
    from market_intel.studio import measurement
    from market_intel.studio_film import providers

    calls = []
    monkeypatch.setattr(providers, "estimate_hero", lambda: {"estimated_usd": 0.48})

    def render(*args, paid, approved_usd):
        calls.append((paid, approved_usd))
        return {"variants": [], "hero": {"id": "demo"}}

    monkeypatch.setattr(studio_film, "render_film", render)
    monkeypatch.setattr(
        measurement, "measure_campaign", lambda dest, result, *args: result
    )
    assert client.post(base + "/film", json={"paid": True}).status_code == 202
    assert finished(client)["film"]["hero"]["id"] == "demo"
    assert (
        client.post(base + "/film", json={"paid": True}).json()["status"] == "complete"
    )
    assert calls == [(True, 0.48)]


def test_readback_records_measured_winner_and_missing_denominators(studio, monkeypatch):
    import market_intel.studio_research as research

    client, folder = studio
    runs.write_json(folder / "creative.json", {"variants": [{"id": "v1"}]})
    observed = {
        "id": "p1",
        "status": "ready",
        "frames": [],
        "url": "https://www.instagram.com/reel/abc/",
    }
    monkeypatch.setattr(research, "deconstruct", lambda *a, **kw: dict(observed))
    monkeypatch.setattr(
        research,
        "readback_baseline",
        lambda *a, **kw: {
            "status": "measured",
            "baseline_n": 50,
            "baseline_median": 500,
            "views": 4000,
            "outlier_ratio": 8,
            "evidence": "outlier-backed",
            "observed_at": "2026-11-21",
        },
    )
    data = {
        "variant_id": "v1",
        "url": observed["url"],
        "observations": {
            "views_3s": 200,
            "impressions": 1000,
            "clicks": 18,
            "spend_inr": 300,
        },
    }
    assert client.post("/studio/runs/example/readback", json=data).status_code == 202
    s = finished(client)
    assert s["readbacks"][0]["metrics"] == {
        "hook_rate": 0.2,
        "hold_rate": None,
        "ctr": 0.018,
        "cpa": None,
    }
    assert s["readbacks"][0]["outlier_ratio"] == 8
    assert s["posts"][0]["evidence"] == "outlier-backed"
