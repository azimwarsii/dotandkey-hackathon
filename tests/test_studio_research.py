from datetime import date

import pytest
from PIL import Image, ImageDraw

from market_intel.studio_research import (
    ad_lifetime,
    deconstruct,
    pattern_board,
    readback_baseline,
    sources,
)


def test_medians_stay_with_account_and_unknown_counts_remain_missing():
    rows = [
        {"creator": "A", "platform": "Instagram", "views": v, "likes": 1, "comments": 1}
        for v in (0, 10, 10, 10, 50, None)
    ]
    rows += [{"creator": "A", "platform": "YouTube", "views": 99999}]
    sources.score_account(rows)
    assert rows[4]["evidence"] == "outlier-backed" and rows[4]["outlier_ratio"] == 5
    assert rows[0]["comment_rate"] is None and rows[4]["share_rate"] is None
    assert rows[5]["outlier_ratio"] is None and rows[6]["outlier_ratio"] is None


def test_url_validation_and_ad_lifetime():
    assert sources.checked_url("https://youtu.be/abcdefghijK?t=25")[1].endswith(
        "watch?v=abcdefghijK"
    )
    for url in (
        "https://www.youtube.com.example.org/watch?v=abcdefghijK",
        "http://127.0.0.1/file.mp4",
        "https://example.net@www.instagram.com/reel/abc/",
        "file:///tmp/a",
    ):
        with pytest.raises(ValueError):
            sources.checked_url(url)
    assert ad_lifetime(date(2020, 1, 1), date(2020, 2, 1))["longevity_signal"] is True
    assert ad_lifetime("2020-01-01", active=False)["observed_days_running"] is None
    with pytest.raises(ValueError):
        ad_lifetime("2022-01-01", "2020-01-01")


def test_owned_post_baseline_excludes_the_target_and_rejects_other_publishers(
    monkeypatch,
):
    target = "https://www.instagram.com/reel/target/"
    item = {"platform": "Instagram", "url": target}
    expected = {"product": {"brand": "Dot & Key"}}
    owner = {"username": "dotandkey.skincare"}
    monkeypatch.setattr(
        sources,
        "_scrape",
        lambda *args, **kwargs: {
            "data": {"xdt_shortcode_media": {"owner": owner, "video_play_count": 999}}
        },
    )
    monkeypatch.setattr(
        sources,
        "instagram_account",
        lambda *args, **kwargs: (
            [{"url": target, "views": 30}]
            + [
                {"url": f"https://www.instagram.com/reel/{i}/", "views": 10}
                for i in range(5)
            ]
        ),
    )
    result = readback_baseline(item, expected)
    assert (
        result["status"] == "measured"
        and result["outlier_ratio"] == 3
        and result["baseline_n"] == 5
    )
    owner["username"] = "another-brand"
    assert readback_baseline(item, expected)["status"] == "unavailable"


def test_real_image_upload_keeps_slide_evidence_and_offline_pattern(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    slide = tmp_path / "poster.png"
    im = Image.new("RGB", (200, 100), "#ff8866")
    ImageDraw.Draw(im).text((10, 10), "Reapply", fill="black")
    im.save(slide)
    post = deconstruct(tmp_path / "run", paths=[slide])
    assert (
        post["status"] == "ready"
        and post["media_type"] == "image"
        and len(post["frames"]) == 1
    )
    assert post["evidence"] == "user-curated" and post["outlier_ratio"] is None
    for key in ("thumbnail", "contact_sheet", "media"):
        assert (tmp_path / "run" / post[key]).is_file()
    (p,) = pattern_board([post])
    assert p["evidence"] == "curated hypothesis"
    assert not p["winning_spec"]["length_iqr"]
    assert p["post_ids"] == [post["id"]] and p["repeatability"] == 0
    assert post == deconstruct(tmp_path / "run", paths=[slide])


def test_link_then_upload_recovers_without_fabricated_coverage(tmp_path, monkeypatch):
    from market_intel.studio_research import analysis

    monkeypatch.setattr(analysis, "_resolve", lambda *args: ([], {}))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    link = "https://www.instagram.com/reel/ABC123/"
    pending = deconstruct(tmp_path, url=link)
    assert pending["status"] == "upload_required" and not pending["frames"]
    slide = tmp_path / "poster.png"
    Image.new("RGB", (120, 90), "white").save(slide)
    post = deconstruct(tmp_path, url=link, paths=[slide])
    assert post["status"] == "ready" and post["id"] == pending["id"]


def test_recommended_sources_require_category_evidence_and_distinct_creators():
    from market_intel.studio_research import recommended_sources

    base = {
        "platform": "Instagram",
        "duration": 20,
        "evidence": "outlier-backed",
        "creator": "A",
        "title": "My sunscreen",
        "outlier_ratio": 6,
    }
    rows = [
        dict(base, url="1"),
        dict(base, url="2", outlier_ratio=7),
        dict(base, url="3", creator="B"),
        dict(base, url="4", creator="C", duration=900),
        dict(base, url="5", creator="Z", title="Another topic"),
    ]
    assert [
        r["url"]
        for r in recommended_sources(rows, {"product": {"category": "Sunscreen"}})
    ] == ["2", "3"]
