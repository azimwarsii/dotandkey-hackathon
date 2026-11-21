import pytest
from fastapi.testclient import TestClient
from PIL import Image

from market_intel.studio_film import providers, shim
from market_intel.studio_film.compose import combine, ffmpeg, qc, segment, shot_card


def test_hero_quote_and_job_resumption(tmp_path, monkeypatch):
    frames = []
    for i in range(2):
        f = tmp_path / f"frame{i}.jpg"
        f.write_bytes(b"image" + bytes([i]))
        frames.append(f)
    quote = {"estimated_usd": 0.48}
    monkeypatch.setattr(providers, "estimate_hero", lambda: quote)
    jobs = []

    class Response:
        content = b"media"

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def request(provider, method, path, **options):
        if method == "POST":
            jobs.append(options["json"])
            return Response({"id": "id-" + str(len(jobs))})
        return Response({"status": "completed"})

    monkeypatch.setattr(providers, "request", request)
    destination = tmp_path / "paid"
    with pytest.raises(ValueError):
        providers.create_hero_clips(destination, frames, ["one", "two"], 0.25)
    assert not jobs
    for _ in range(2):
        _, output = providers.create_hero_clips(
            destination, frames, ["one", "two"], 0.48
        )
        assert all(f.read_bytes() == b"media" for f in output)
    assert len(jobs) == 2 and not jobs[0]["generate_audio"]
    with pytest.raises(ValueError, match="input has changed"):
        providers.create_hero_clips(destination, frames, ["changed", "two"], 0.48)


def test_clipforge_shim_speech_image_and_video_contract(monkeypatch):
    monkeypatch.setenv("STUDIO_SHIM_TOKEN", "local-only")
    calls = []

    class Result:
        content = b"mp4"

        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data

    def send(provider, method, path, **opts):
        calls.append((path, opts))
        return Result(
            {"data": [{"b64_json": "QQ=="}]}
            if path == "/images"
            else {"id": "vid", "status": "pending"}
        )

    monkeypatch.setattr(shim, "request", send)
    monkeypatch.setattr(
        shim, "sarvam_speech", lambda line, lang, voice, codec: b"voice"
    )
    with TestClient(shim.app) as c:
        assert c.post("/v1/videos", json={}).status_code == 401
        c.headers["authorization"] = "Bearer local-only"
        assert (
            c.post(
                "/v1/audio/speech", json={"input": "A line.", "voice": "alloy"}
            ).content
            == b"voice"
        )
        assert (
            c.post(
                "/v1/images/edits",
                data={"prompt": "Board", "size": "1024x1024"},
                files={"image[]": ("pack.png", b"photo", "image/png")},
            ).json()["data"][0]["b64_json"]
            == "QQ=="
        )
        payload = calls[-1][1]["json"]
        assert payload["aspect_ratio"] == "1:1" and payload["input_references"][0][
            "image_url"
        ]["url"].startswith("data:image/png;")
        r = c.post(
            "/v1/videos",
            data={"prompt": "Demo", "seconds": "8", "size": "720x1280"},
            files={"input_reference": ("first.jpg", b"pack", "image/jpeg")},
        )
        assert r.json() == {"id": "vid", "status": "queued"}
        assert calls[-1][1]["json"]["frame_images"][0]["frame_type"] == "first_frame"
        assert c.get("/v1/videos/vid").json()["status"] == "queued"
        assert c.get("/v1/videos/vid/content").content == b"mp4"


def test_offline_composition_is_decodable_and_timed(tmp_path):
    photo = tmp_path / "pack.png"
    Image.new("RGBA", (40, 90), "pink").save(photo)
    brief = {
        "product": {
            "cutout": "pack.png",
            "handle": "test",
            "local_images": ["pack.png"],
        }
    }
    shot = {"text": "Meet the pack.", "vo": "Meet the pack.", "duration": 1.0}
    frame = tmp_path / "frame.jpg"
    shot_card(tmp_path, brief, shot, 0, "demo", frame)
    speech = tmp_path / "voice.wav"
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=360:duration=0.8", speech)
    clip = tmp_path / "shot.mp4"
    segment(frame, speech, 1, clip)
    final = tmp_path / "master.mp4"
    combine([clip], final)
    report = qc(final, {"shots": [shot], "cta": "Explore"}, tmp_path / "sheet.jpg")
    assert report["status"] == "pass" and (tmp_path / "sheet.jpg").stat().st_size > 1000


def test_free_rerender_keeps_the_paid_master_and_exports(tmp_path, monkeypatch):
    import hashlib
    import json

    import market_intel.studio_film as film

    script = {"id": "hero-script"}
    digest = hashlib.sha256(
        json.dumps(script, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    hero = {
        "id": "hero",
        "video": "hero.mp4",
        "exports": {"reels": "reels.mp4"},
        "storyboard": "storyboard.jpg",
        "contact_sheet": "contact.jpg",
        "gate": {"status": "pass"},
        "qc": {"status": "pass"},
        "recipe": {},
        "clipforge": {},
    }
    for key in ["hero.mp4", "reels.mp4"]:
        (tmp_path / key).write_bytes(b"existing")
    quote = {"estimated_usd": 0.48}
    providers.save_json(
        tmp_path / "film.json", {"script_hash": digest, "hero": hero, "quote": quote}
    )
    monkeypatch.setattr(
        film.httpx, "get", lambda *a, **kw: type("Response", (), {"status_code": 503})()
    )
    monkeypatch.setattr(film, "_render", lambda *a, **kw: {"id": "draft"})
    variant = {"id": "draft", "title": "Draft", "format": "presenter", "script": script}
    result = film.render_film(tmp_path, {}, script, [variant])
    assert result["hero"] == hero and result["quote"] == quote
    assert result["video"] == "hero.mp4" and result["exports"] == {"reels": "reels.mp4"}


def test_reference_rhythm_uses_local_media_and_falls_back_to_saved_cuts(tmp_path):
    import json

    from market_intel.studio_film.reference import match_reference

    post = {
        "id": "ref",
        "media": "missing.mp4",
        "shots": [{"duration": 1.2}, {"duration": 3.4}],
    }
    dest = tmp_path / "campaign"
    assert match_reference(tmp_path, None, dest) is None
    assert not dest.exists()
    selected = match_reference(tmp_path, post, dest)
    assert selected["shots"] == post["shots"]
    assert (
        json.loads((dest / "reference-rhythm.json").read_text())["source"]
        == "saved research scene cuts"
    )


def test_reference_analysis_uploads_the_selected_video_and_applies_generation_beats(
    tmp_path, monkeypatch
):
    import httpx

    from market_intel.studio_film import reference

    local = tmp_path / "reference.mp4"
    local.write_bytes(b"fixture-video-bytes")
    beats = [{"start": 0, "duration": 2.5}, {"start": 2.5, "duration": 3.5}]
    cuts = [{"start": 0, "duration": 1.3}, {"start": 1.3, "duration": 1.2}, beats[1]]

    def endpoint(request):
        assert request.url.path == "/api/replicate/analyze"
        assert (
            b'name="file"' in request.content and local.read_bytes() in request.content
        )
        return httpx.Response(
            200, json={"duration": 6, "shots": cuts, "generationBeats": beats}
        )

    client = httpx.Client
    monkeypatch.setattr(
        reference.httpx,
        "Client",
        lambda **kw: client(transport=httpx.MockTransport(endpoint), **kw),
    )
    result = reference.match_reference(
        tmp_path, {"id": "ref", "media": local.name, "shots": cuts}, tmp_path
    )
    assert result["shots"] == beats
    assert result["rhythm"]["source_cuts"] == cuts
