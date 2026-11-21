"""Package the currently selected campaign's deliverables."""

import json
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from . import runs


def brief_text(brief, creative):
    product = brief.get("product", {})
    lines = [
        "Dot & Key campaign brief",
        product.get("title") or "Campaign",
        brief.get("as_of"),
        product.get("url"),
    ]
    evidence = brief.get("market_evidence")
    if evidence:
        lines.extend(["", "Campaign starting point", evidence.get("title")])
    lines.extend(["", "Catalog wording", *brief.get("allowed_claims", [])])
    audience = brief.get("audience", {})
    for title, key in [
        ("4–5 star product reviews", "top_desires"),
        ("1–2 star product reviews", "top_objections"),
        ("Category review examples", "category_objections"),
    ]:
        lines.extend(["", title])
        rows = audience.get(key) or []
        for row in rows:
            lines.extend(
                [
                    row.get("quote"),
                    f"{row.get('rating', '—')} / 5 · {row.get('platform') or 'Review'}",
                    row.get("source"),
                ]
            )
        if not rows:
            lines.append("No sampled quotes in this group.")
    script = creative.get("script") or {}
    if script.get("shots"):
        lines.extend(["", "Script and storyboard", script.get("title")])
        for shot in script["shots"]:
            lines.extend(
                [
                    "",
                    f"{shot.get('start', 0)}s · {shot.get('duration', 0)} seconds",
                    shot.get("visual"),
                    "On screen — " + (shot.get("text") or ""),
                    "Voiceover — " + (shot.get("vo") or ""),
                ]
            )
    for listing in creative.get("listings", []):
        lines.extend(
            [
                "",
                listing.get("market"),
                listing.get("title"),
                *listing.get("bullets", []),
                listing.get("description"),
            ]
        )
    return "\n".join(str(line) for line in lines if line is not None) + "\n"


def archive(folder):
    campaign = runs.campaign_dir(folder).resolve()
    creative = runs.load(campaign / "creative.json", {})
    film = runs.load(campaign / "film.json", {})
    if not creative.get("script"):
        raise ValueError("Produce a concept to download its campaign kit.")
    files = {
        row["path"] for row in creative.get("statics", []) + creative.get("aplus", [])
    }
    for row in [film.get("hero") or {}, *film.get("variants", [])]:
        files.update(row.get("exports", {}).values())
        files.update(row.get(k) for k in ("video", "contact_sheet", "storyboard"))
    social = film.get("social", {})
    files.update(
        [
            film.get("director", {}).get("image"),
            social.get("cover"),
            *social.get("carousel", []),
        ]
    )
    files.update(
        p.relative_to(campaign).as_posix()
        for p in (campaign / "locales").glob("*.json")
    )
    stream = SpooledTemporaryFile(max_size=2**20)  # noqa: SIM115 - caller streams and closes it
    try:
        with ZipFile(stream, "w", ZIP_DEFLATED, compresslevel=1) as out:
            brief = runs.load(campaign / "brief.json") or runs.load(
                folder / "brief.json", {}
            )
            if brief.get("product"):
                out.writestr("Campaign brief.txt", brief_text(brief, creative))
            for key in ("script", "listings", "test_plan", "lineage", "variants"):
                if key in creative:
                    out.writestr(
                        key + ".json",
                        json.dumps(creative[key], ensure_ascii=False, indent=2),
                    )
            source = runs.load(folder / "run.json", {}).get("evidence")
            if source:
                out.writestr(
                    "market-evidence.json",
                    json.dumps(source, ensure_ascii=False, indent=2),
                )
            for name in sorted(n for n in files if isinstance(n, str)):
                path = (campaign / name).resolve()
                if (
                    campaign in path.parents
                    and path.is_file()
                    and not Path(name).is_absolute()
                ):
                    out.write(path, path.relative_to(campaign))
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
