"""Package the currently selected campaign's deliverables."""

import json
from pathlib import Path
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from . import runs


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
