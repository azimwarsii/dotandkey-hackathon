import io
from zipfile import ZipFile

from fastapi.testclient import TestClient

from market_intel import studio_creative
from market_intel.api import app
from market_intel.frontend_api import evidence
from market_intel.studio import runs, throttle


def test_kit_contains_only_current_deliverables(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_RUNS_DIR", str(tmp_path))
    root = tmp_path / "run-id"
    runs.write_json(
        root / "run.json", {"id": "run-id", "evidence": {"id": "market-source"}}
    )
    runs.write_json(root / "selected.json", {"directory": "campaigns/a"})
    campaign = root / "campaigns/a"
    (campaign / "ads").mkdir(parents=True)
    (campaign / "ads/ad.png").write_bytes(b"ad")
    runs.write_json(
        campaign / "creative.json",
        {
            "script": {"id": "script"},
            "statics": [{"path": "ads/ad.png"}, {"path": "../../run.json"}],
            "test_plan": {"tests": 3},
        },
    )
    response = TestClient(app).get("/studio/runs/run-id/kit.zip")
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {
            "ads/ad.png",
            "test_plan.json",
            "script.json",
            "market-evidence.json",
        }


def test_evidence_is_verified_and_category_constrained(tmp_path, monkeypatch):
    from market_intel.studio import api

    monkeypatch.setenv("STUDIO_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr(
        api, "products", lambda: [{"handle": "gel", "category": "Sunscreen"}]
    )
    record = {
        "id": "forecast",
        "category": "Sunscreen",
        "as_of": "2026-11-21",
        "title": "Observed market signal",
    }
    monkeypatch.setattr(
        evidence,
        "resolve_evidence",
        lambda name, day, key: record if key == "forecast" else None,
    )
    monkeypatch.setattr(
        studio_creative,
        "build_brief",
        lambda *args, **kwargs: {"product": {"handle": "gel"}},
    )
    client = TestClient(app)
    reply = client.post(
        "/studio/runs", json={"evidence": {**record, "title": "unverified text"}}
    )
    assert reply.status_code == 202
    folder = runs.run_path(reply.json()["id"])
    import time

    for _ in range(100):
        if (folder / "brief.json").exists():
            break
        time.sleep(0.01)
    assert runs.load(folder / "brief.json")["market_evidence"] == record
    assert (
        client.post(
            "/studio/runs", json={"evidence": {**record, "id": "unknown"}}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/studio/runs", json={"evidence": record, "handle": "other"}
        ).status_code
        == 404
    )


def test_generation_window_is_shared_and_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDIO_RUNS_DIR", str(tmp_path / "runs"))
    assert throttle.allowed("client", 1)
    assert not throttle.allowed("client", 1)
    assert throttle.allowed("another", 1)
    assert throttle.is_generation("/api/ask")
    assert not throttle.is_generation("/studio/runs/example/kit.zip")
