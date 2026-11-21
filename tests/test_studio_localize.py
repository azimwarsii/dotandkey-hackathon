from market_intel.studio_creative.localize import localize


def _inputs():
    return (
        {
            "claim_sources": [
                {"id": "f1", "text": "SPF 50+"},
                {"id": "f2", "text": "Quick-absorbing"},
            ]
        },
        {
            "script": {
                "shots": [
                    {
                        "id": "s1",
                        "text": "SPF 50+",
                        "vo": "Quick-absorbing",
                        "line_refs": {"vo": "f2", "text": "f1"},
                        "insight_ref": "f1",
                    }
                ]
            },
            "listings": [],
        },
    )


def test_translation_blocks_changes_to_spf_and_caches_per_language(
    tmp_path, monkeypatch
):
    calls = []
    monkeypatch.setenv("SARVAM_API_KEY", "test")

    def fake(client, text, src, dst, **kw):
        calls.append((text, src, kw))
        if src == "hi-IN":
            return ("SPF 30+" if "30" in text else "Quick-absorbing", "back")
        return ("एसपीएफ 30+" if "50" in text else "तेजी से अवशोषित", "forward")

    monkeypatch.setattr("market_intel.studio_creative.localize._translate", fake)
    brief, creative = _inputs()
    report = localize(tmp_path, brief, creative, "hi-IN")
    row = report["lines"][0]
    assert row["translation"] is None and row["status"] == "blocked"
    assert row["fact_refs"] == ["f1"] and report["lines"][1]["translation"]
    assert not report["publishable"] and report["summary"]["pending_review"] == 1
    assert len(calls) == 4
    monkeypatch.delenv("SARVAM_API_KEY")
    assert localize(tmp_path, brief, creative, "hi-IN") == report and len(calls) == 4
    monkeypatch.setenv("SARVAM_API_KEY", "test")
    assert localize(tmp_path, brief, creative, "hinglish")["language"] == "hi-Latn"
    assert any(
        kwargs.get("roman") is True and kwargs["mode"] == "code-mixed"
        for _, _, kwargs in calls
    )


def test_changed_source_must_match_locked_evidence(tmp_path, monkeypatch):
    brief, creative = _inputs()
    monkeypatch.setenv("SARVAM_API_KEY", "test")
    monkeypatch.setattr(
        "market_intel.studio_creative.localize._translate",
        lambda *args, **kw: ("demo", "id"),
    )
    creative["script"]["shots"][0]["text"] = "100% safe"
    r = localize(tmp_path, brief, creative, "hi-IN")
    assert (
        "Source differs" in r["lines"][0]["flags"][0]
        and not r["lines"][0]["translation"]
    )


def test_reversed_claim_cannot_be_used_as_translated_copy():
    from market_intel.studio_creative.localize import _review

    blockers, _, _ = _review("zero white cast", "सफेद परत", "leaves a white cast")
    assert any("direction" in reason for reason in blockers)
