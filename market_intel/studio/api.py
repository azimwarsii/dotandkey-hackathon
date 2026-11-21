"""Local studio API. Long-running research and renders return a pollable job."""
# Pydantic evaluates these endpoint types at runtime on supported Python 3.9.
# ruff: noqa: FA100

import math
import shutil
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from market_intel.store import Store

from . import runs


def local_operator(request: Request):
    origin = request.headers.get("origin")
    if origin and request.method not in {"GET", "HEAD", "OPTIONS"}:
        permitted = {
            f"{request.url.scheme}://{request.url.netloc}",
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        }
        if origin not in permitted:
            raise HTTPException(403, "Open the local studio to change this campaign.")


router = APIRouter(
    prefix="/studio", tags=["content studio"], dependencies=[Depends(local_operator)]
)
UPLOADS = {".mp4", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".webp"}
ASSETS = UPLOADS | {
    ".vtt",
    ".srt",
    ".wav",
    ".mp3",
    ".svg",
    ".json",
    ".pdf",
    ".zip",
    ".csv",
    ".html",
    ".txt",
    ".woff",
    ".woff2",
}
PLATFORMS = {
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "facebook.com",
    "fb.watch",
}


class NewRun(BaseModel):
    handle: str = Field(min_length=1, max_length=180)


class Source(BaseModel):
    url: Optional[str] = None
    uploads: list[str] = Field(default_factory=list, max_length=10)
    ad_start: Optional[date] = None
    ad_end: Optional[date] = None
    ad_active: bool = False


class Choice(BaseModel):
    concept_id: str
    reference_id: Optional[str] = None


class FilmRequest(BaseModel):
    paid: bool = False
    approved_usd: Optional[float] = Field(default=None, gt=0, le=10)


class Readback(BaseModel):
    variant_id: str
    url: str
    observations: dict[str, float] = Field(default_factory=dict)


class Localization(BaseModel):
    language: str


def folder_for(run_id):
    try:
        path = runs.run_path(run_id)
    except ValueError:
        raise HTTPException(404, "Unknown run")
    if not path.is_dir() or not (path / "run.json").is_file():
        raise HTTPException(404, "Unknown run")
    return path


def launch(folder, action, task):
    try:
        return runs.submit(folder, action, task)
    except runs.Busy as exc:
        raise HTTPException(409, str(exc)) from exc


def social_url(url):
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        okay = (
            parts.scheme == "https"
            and not parts.username
            and not parts.password
            and parts.port in (None, 443)
        )
    except ValueError:
        okay = False
    if not okay or not any(host == h or host.endswith("." + h) for h in PLATFORMS):
        raise HTTPException(
            422,
            "Provide an HTTPS post URL from Instagram, YouTube, Facebook or TikTok.",
        )
    return url


def need_brief(folder):
    brief = runs.load(folder / "brief.json")
    if not brief:
        raise HTTPException(409, "Build the product brief first.")
    return brief


def select(items, key, label):
    row = next((r for r in items if r.get("id") == key), None)
    if row is None:
        raise HTTPException(404, "Unknown " + label)
    return row


def seed_files(data, folder, dest):
    """Make referenced local inputs available to versioned, self-contained generations."""
    if isinstance(data, dict):
        for v in data.values():
            seed_files(v, folder, dest)
    elif isinstance(data, list):
        for v in data:
            seed_files(v, folder, dest)
    elif (
        isinstance(data, str)
        and 0 < len(data) < 400
        and not data.startswith(("/", "."))
    ):
        rel = Path(data)
        if ".." in rel.parts or rel.suffix.lower() not in ASSETS:
            return
        src = (folder / rel).resolve()
        if folder.resolve() in src.parents and src.is_file():
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            if not out.exists():
                shutil.copy2(src, out)


@router.get("/products")
def products():
    with closing(Store(runs.db_paths()[0])) as store:
        return [
            {
                "handle": p["handle"],
                "title": p["title"],
                "category": p["category"],
                "image": (p.get("images") or [None])[0],
            }
            for p in store.catalog()
            if not p["is_combo"]
        ]


@router.get("/runs")
def list_runs():
    return [
        runs.load(p)
        for p in sorted(
            runs.root().glob("*/run.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    ]


@router.post("/runs", status_code=202)
def new_run(body: NewRun):
    if not any(p["handle"] == body.handle for p in products()):
        raise HTTPException(404, "Unknown product handle")
    run_id = uuid4().hex[:14]
    folder = runs.run_path(run_id)
    folder.mkdir(parents=True, exist_ok=False)
    runs.write_json(
        folder / "run.json",
        {"id": run_id, "handle": body.handle, "created_at": runs.timestamp()},
    )
    return {"id": run_id, "job": build_brief(run_id)}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return runs.snapshot(folder_for(run_id))


@router.post("/runs/{run_id}/brief", status_code=202)
def build_brief(run_id: str):
    folder = folder_for(run_id)

    def work():
        from market_intel.studio_creative import build_brief as build

        handle = runs.load(folder / "run.json")["handle"]
        runs.write_json(folder / "brief.json", build(handle, *runs.db_paths(), folder))

    return launch(folder, "Product brief", work)


@router.get("/runs/{run_id}/assets/{asset_path:path}")
def asset(run_id: str, asset_path: str):
    folder = folder_for(run_id)
    path = (folder / asset_path).resolve()
    if (
        folder not in path.parents
        or not path.is_file()
        or path.suffix.lower() not in ASSETS
        or any(part.startswith(".") for part in Path(asset_path).parts)
    ):
        raise HTTPException(404, "Unknown asset")
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
    }
    return FileResponse(path, headers=headers)


@router.post("/runs/{run_id}/uploads", status_code=201)
async def upload(request: Request, run_id: str, filename: str):
    folder = folder_for(run_id)
    suffix = Path(filename).suffix.lower()
    if suffix not in UPLOADS:
        raise HTTPException(415, "Use a video or an image file.")
    directory = folder / "uploads"
    directory.mkdir(exist_ok=True)
    key = uuid4().hex + suffix
    target = directory / key
    size = 0
    try:
        with target.open("xb") as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > 48 * 1024**2:
                    raise HTTPException(413, "Maximum file size is 48 MiB.")
                stream.write(chunk)
        if not size:
            raise HTTPException(422, "Empty upload")
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return {"id": key, "bytes": size}


@router.post("/runs/{run_id}/deconstruct", status_code=202)
def deconstruct(run_id: str, body: Source):
    folder = folder_for(run_id)
    if not body.url and not body.uploads:
        raise HTTPException(422, "Choose a post link or uploaded files.")
    url = social_url(body.url) if body.url else None
    if body.ad_end and (not body.ad_start or body.ad_end < body.ad_start):
        raise HTTPException(422, "Ad dates must be in chronological order.")
    if body.ad_active and (body.ad_end or not body.ad_start):
        raise HTTPException(
            422, "An active ad needs its start date and an open end date."
        )
    paths = []
    for key in body.uploads:
        if (
            Path(key).name != key
            or key.startswith(".")
            or not (folder / "uploads" / key).is_file()
        ):
            raise HTTPException(404, "Unknown upload")
        paths.append(folder / "uploads" / key)

    def work():
        from market_intel.studio_research import deconstruct as analyze

        brief = runs.load(folder / "brief.json", {})
        images = brief.get("product", {}).get("local_images") or []
        post = analyze(
            folder,
            url=url,
            paths=paths or None,
            product_image=(folder / images[0]) if images else None,
        )
        if body.ad_start:
            from market_intel.studio_research.sources import ad_lifetime

            post["ad_lifetime"] = {
                **ad_lifetime(
                    body.ad_start.isoformat(),
                    body.ad_end.isoformat() if body.ad_end else None,
                    body.ad_active,
                ),
                "start_date": body.ad_start.isoformat(),
                "end_date": body.ad_end.isoformat() if body.ad_end else None,
                "active": body.ad_active,
                "provenance": "user-transcribed Ad Library dates",
            }
            runs.write_json(folder / "research" / post["id"] / "post.json", post)
        runs.refresh_patterns(folder)

    return launch(folder, "Deconstruct source", work)


@router.post("/runs/{run_id}/discover", status_code=202)
def discover(run_id: str):
    folder = folder_for(run_id)
    brief = need_brief(folder)

    def work():
        from market_intel.studio_research import (
            deconstruct as analyze,
        )
        from market_intel.studio_research import (
            discover as find,
        )
        from market_intel.studio_research import (
            recommended_sources,
        )

        result = find(folder, brief)
        if not (folder / "research/discovery.json").is_file():
            runs.write_json(folder / "research/discovery.json", result)
        if not any(p.get("status") == "ready" for p in runs.posts_in(folder)):
            photos = brief["product"].get("local_images", [])
            for candidate in recommended_sources(result, brief, limit=2):
                analyze(
                    folder,
                    url=candidate["url"],
                    product_image=(folder / photos[0]) if photos else None,
                )
        runs.refresh_patterns(folder)

    return launch(folder, "Discover posts", work)


@router.post("/runs/{run_id}/concepts", status_code=202)
def concepts(run_id: str):
    folder = folder_for(run_id)
    brief = need_brief(folder)

    def work():
        from market_intel.studio_creative import concepts as build

        runs.write_json(
            folder / "concepts.json",
            build(brief, runs.refresh_patterns(folder), run_dir=folder),
        )

    return launch(folder, "Concept slate", work)


@router.post("/runs/{run_id}/generate", status_code=202)
def generate(run_id: str, body: Choice):
    folder = folder_for(run_id)
    brief = need_brief(folder)
    state = runs.snapshot(folder)
    concept = select(state["concepts"], body.concept_id, "concept")
    reference = (
        select(state["posts"], body.reference_id, "reference")
        if body.reference_id
        else None
    )

    def work():
        from market_intel.studio_creative import generate as build
        from market_intel.studio_film.reference import match_reference

        rel = "campaigns/" + uuid4().hex[:12]
        dest = folder / rel
        dest.mkdir(parents=True)
        seed_files([brief, reference], folder, dest)
        runs.write_json(dest / "brief.json", brief)
        runs.write_json(dest / "concepts.json", state["concepts"])
        runs.write_json(dest / "patterns.json", state["patterns"])
        rhythm = match_reference(folder, reference, dest)
        result = build(dest, brief, state["patterns"], concept, reference=rhythm)
        runs.write_json(dest / "creative.json", result)
        runs.write_json(
            folder / "selected.json",
            {
                "concept_id": body.concept_id,
                "reference_id": body.reference_id,
                "directory": rel,
            },
        )

    return launch(folder, "Generate campaign", work)


@router.post("/runs/{run_id}/localize", status_code=202)
def localize(run_id: str, body: Localization):
    from market_intel.studio_creative.localize import LANGUAGES
    from market_intel.studio_creative.localize import localize as translate

    folder = folder_for(run_id)
    brief = need_brief(folder)
    dest = runs.campaign_dir(folder)
    creative = runs.load(dest / "creative.json", {})
    if body.language not in LANGUAGES:
        raise HTTPException(422, "Select Hindi or Hinglish.")
    if not creative.get("script"):
        raise HTTPException(409, "Generate a script first.")
    return launch(
        folder,
        "Adapt copy into " + LANGUAGES[body.language],
        lambda: translate(dest, brief, creative, body.language),
    )


@router.post("/runs/{run_id}/film", status_code=202)
def film(run_id: str, body: FilmRequest):
    folder = folder_for(run_id)
    brief = need_brief(folder)
    dest = runs.campaign_dir(folder)
    creative = runs.load(dest / "creative.json", {})
    if not creative.get("script"):
        raise HTTPException(409, "Generate a script first.")
    if body.paid and body.approved_usd is None:
        raise HTTPException(422, "A paid render needs the displayed quote.")

    def work():
        from market_intel.studio_film import render_film

        result = render_film(
            dest,
            brief,
            creative["script"],
            creative["variants"],
            paid=body.paid,
            approved_usd=body.approved_usd,
        )
        from .measurement import measure_campaign

        patterns = runs.load(
            dest / "patterns.json", runs.load(folder / "research/patterns.json", [])
        )
        runs.write_json(
            dest / "film.json",
            measure_campaign(dest, result, creative, patterns, brief),
        )

    return launch(
        folder, "Render hero film" if body.paid else "Render draft variants", work
    )


@router.post("/runs/{run_id}/readback", status_code=202)
def readback(run_id: str, body: Readback):
    folder = folder_for(run_id)
    state = runs.snapshot(folder)
    variant = select(state["creative"].get("variants", []), body.variant_id, "variant")
    url = social_url(body.url)
    valid = {
        "impressions",
        "views_3s",
        "completed_views",
        "clicks",
        "spend_inr",
        "acquisitions",
    }
    for k, v in body.observations.items():
        if (
            k not in valid
            or not math.isfinite(v)
            or v < 0
            or (k != "spend_inr" and not float(v).is_integer())
        ):
            raise HTTPException(422, "Invalid performance observation")

    def work():
        from market_intel.studio_research import deconstruct as analyze

        post = analyze(folder, url=url)
        if post.get("status") != "ready":
            raise ValueError("The live post could not be resolved.")
        from market_intel.studio_research import readback_baseline

        baseline = readback_baseline(post, state["brief"])
        if baseline.get("status") == "measured":
            post.update(
                {
                    k: baseline[k]
                    for k in (
                        "views",
                        "baseline_n",
                        "baseline_median",
                        "outlier_ratio",
                        "evidence",
                    )
                }
            )
            post["performance_observed_at"] = baseline["observed_at"]
            runs.write_json(folder / "research" / post["id"] / "post.json", post)
        history = runs.load(folder / "readback.json", [])
        history.append(
            {
                "id": uuid4().hex[:12],
                "variant_id": variant["id"],
                "url": url,
                "post_id": post["id"],
                "concept_id": state["selected"].get("concept_id"),
                "observed_at": runs.timestamp(),
                "outlier_ratio": baseline.get("outlier_ratio"),
                "baseline": baseline,
                "observation_source": "user-entered platform metrics",
                "observations": body.observations,
                "metrics": runs.readback_metrics(body.observations),
            }
        )
        runs.write_json(folder / "readback.json", history)
        runs.refresh_patterns(folder)

    return launch(folder, "Measure published variant", work)


@router.get("/film-quote")
def film_quote():
    from market_intel.studio_film.providers import estimate_hero

    return estimate_hero()
