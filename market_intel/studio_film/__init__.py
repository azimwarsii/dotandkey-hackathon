"""Grounded campaign-film renderer, with explicit spend and review gates."""

import hashlib
import json
import os
import re
from pathlib import Path

import httpx

from market_intel.studio.runs import progress

from .compose import (
    combine,
    platform_exports,
    qc,
    safe_file,
    segment,
    shot_card,
    shot_evidence,
    storyboard,
    voice_audio,
)
from .providers import create_hero_clips, estimate_hero, save_json
from .sidecar import (
    cover_and_carousel,
    import_verified_board,
    media_adapter,
    render_sidecar,
)


def hero_quote():
    return estimate_hero()


def _render(
    run,
    brief,
    script,
    ident,
    title,
    fmt,
    *,
    movies=None,
    upstream=None,
    judge=False,
    adapter=None,
):
    from market_intel.studio_creative.copy import claim_guard

    if not re.fullmatch(r"[\w-]{1,80}", ident):
        raise ValueError("Invalid film identifier")
    shots = script.get("shots") or []
    if not 1 <= len(shots) <= 40:
        raise ValueError("Film requires 1–40 shots")
    guard = claim_guard(
        [shot.get(k, "") for shot in shots for k in ("text", "vo")], brief
    )
    if guard["issues"]:
        raise ValueError("A script line exceeds the locked fact sheet")
    if not all(
        s.get("insight_ref")
        and s.get("pattern_ref")
        and 0.2 <= float(s.get("duration", 0)) <= 60
        for s in shots
    ):
        raise ValueError(
            "Each shot needs valid duration, insight and pattern references"
        )
    folder = run / "film" / ident
    folder.mkdir(parents=True, exist_ok=True)
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                "catalog-actions-v3" if movies else "tonal-bed-v1",
                brief["product"].get("handle"),
                script,
                fmt,
                bool(movies),
                upstream,
            ],
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    manifest = folder / "result.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        if data.get("fingerprint") == fingerprint and safe_file(run, data.get("video")):
            return data
    paths = []
    frames = []
    timing = []
    sources = []
    duration = sum(float(s["duration"]) for s in shots)
    pos = 0.0
    phase = "hero" if movies else "drafts"
    for idx, shot in enumerate(shots):
        progress(
            f"{title} · adding picture and narration to shot {idx + 1} of {len(shots)}",
            phase=phase,
            completed=idx,
            total=len(shots),
            unit="shots assembled",
        )
        frame = folder / f"shot-{idx + 1:02}.jpg"
        shot_card(run, brief, shot, idx, fmt, frame)
        frames.append(frame)
        overlay = frame
        if movies:
            overlay = folder / f"overlay-{idx + 1:02}.png"
            shot_card(run, brief, shot, idx, fmt, overlay, transparent=True)
        voice, provider = voice_audio(
            shot["vo"],
            run / "film" / "voices",
            script.get("language", "en"),
            paid=bool(movies),
            adapter=adapter,
        )
        clip = folder / f"shot-{idx + 1:02}.mp4"
        movietime = 16 * pos / duration
        info = segment(
            overlay,
            voice,
            shot["duration"],
            clip,
            movies[min(1, int(movietime / 8))] if movies else None,
            movietime % 8,
        )
        source_path, depicted, deviation = (
            shot_evidence(run, brief, shot)
            if movies
            else (shot.get("image"), "Catalog-photo draft animatic", None)
        )
        timing.append(
            {
                **info,
                "planned_visual": shot["visual"],
                "delivered_visual": depicted,
                "visual_source": source_path,
                "visual_deviation": deviation,
                "start": round(pos, 3),
                "shot_id": shot.get("id"),
                "insight_ref": shot["insight_ref"],
                "pattern_ref": shot["pattern_ref"],
                "vo": shot["vo"],
                "text": shot["text"],
            }
        )
        paths.append(clip)
        sources.append(provider)
        pos += shot["duration"]
    master = folder / "master.mp4"
    progress(
        f"{title} · joining shots and checking sound",
        phase=phase,
        completed=len(shots),
        total=len(shots),
        unit="shots assembled",
    )
    combine(paths, master)
    board = folder / "storyboard.jpg"
    storyboard(frames, board)
    sidecar = {"status": "unconfigured"}
    if upstream:
        try:
            progress(
                f"{title} · composing the alternate edit in ClipForge", phase=phase
            )
            sidecar = render_sidecar(
                upstream,
                brief,
                script,
                paths,
                folder / "sidecar",
                judges=judge,
                exports=bool(movies),
            )
            sidecar["status"] = "completed"
            for k in ("contact_sheet", "video"):
                if k in sidecar:
                    sidecar[k] = (
                        (folder / "sidecar" / sidecar[k]).relative_to(run).as_posix()
                    )
            if "exports" in sidecar:
                sidecar["exports"] = {
                    k: (folder / "sidecar" / v).relative_to(run).as_posix()
                    for k, v in sidecar["exports"].items()
                }
        except (
            httpx.HTTPError,
            ValueError,
            RuntimeError,
            TimeoutError,
            KeyError,
        ) as error:
            sidecar = {"status": "unavailable", "reason": str(error)[:300]}
    rel = lambda p: p.relative_to(run).as_posix()
    # ClipForge's alternate is supplied alongside the timed master. Validate the exact exposed file.
    sheet = folder / "contact.jpg"
    progress(f"{title} · checking video, audio and captions", phase=phase)
    checks = qc(master, script, sheet)
    if movies:
        board.write_bytes(sheet.read_bytes())
    gate = {
        "status": checks["status"],
        "claim_guard": guard,
        "technical_qc": checks["status"],
        "upstream": sidecar.get("gate", {}).get("report", {}).get("status"),
        "commercial_review": "Brand and talent clearance required before publication.",
    }
    if gate["upstream"] == "fail":
        gate["status"] = "fail"
    elif gate["upstream"] == "warn" and gate["status"] == "pass":
        gate["status"] = "warn"
    exports = {}
    if movies and gate["status"] != "fail":
        exports = {
            name: rel(path) for name, path in platform_exports(master, folder).items()
        }
    result = {
        "id": ident,
        "title": title,
        "format": fmt,
        "video": rel(master),
        "storyboard": rel(board),
        "contact_sheet": rel(sheet),
        "exports": exports,
        "checks": checks,
        "qc": checks,
        "gate": gate,
        "shots": timing,
        "duration": checks["duration"],
        "inputs": {
            "script_id": script["id"],
            "product_url": brief["product"]["url"],
            "product_photo": brief["product"].get("cutout"),
        },
        "recipe": {
            "composition": "FFmpeg matched to approved shot timings",
            "clipforge": sidecar["status"],
            "narration": sorted(set(sources)),
            "soundtrack": "Original synthesized F-major underscore",
            "visuals": "Veo 3.1 Lite moving background with original Shopify pack composited on every frame"
            if movies
            else "Animated catalog photo animatic",
            "paid_video_usd": 0 if not movies else None,
        },
        "clipforge": sidecar,
        "fingerprint": fingerprint,
    }
    save_json(manifest, result)
    return result


def _hero(run, brief, script, upstream, approved_usd):
    root = run / "film"
    from market_intel.studio_creative.copy import claim_guard

    if claim_guard([s[k] for s in script["shots"] for k in ("text", "vo")], brief)[
        "issues"
    ]:
        raise ValueError("Hero script has unresolved product claims.")
    folder = root / "generation"
    folder.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(2):
        path = folder / f"reference-{i + 1}.jpg"
        shot_card(
            run,
            brief,
            script["shots"][min(i, len(script["shots"]) - 1)],
            i,
            "demo",
            path,
            clean=True,
        )
        frames.append(path)
    prompts = [
        "A premium studio product film, gentle continuous dolly inward. Use this exact photographed package as the fixed subject. Soft sunlight and gentle shadows drift over the blush background. Preserve the exact bottle and label. No new typography, ingredients, hands or graphic overlays.",
        "A premium beauty tabletop film based on this exact product frame. Camera holds the package steady while a subtle warm reflection passes over the coral backdrop. Preserve the real pack proportions and printed label. No added objects, text or graphics.",
    ]
    with (
        media_adapter() as (base, _, token),
        httpx.Client(
            base_url=base,
            headers={"Authorization": "Bearer " + token},
            trust_env=False,
            timeout=180,
        ) as adapter,
    ):
        quote, movies = create_hero_clips(
            folder, frames, prompts, approved_usd, adapter=adapter
        )
        hero = _render(
            run,
            brief,
            script,
            "hero",
            "Campaign film",
            "demo",
            movies=movies,
            upstream=upstream,
            judge=False,
            adapter=adapter,
        )
    hero["recipe"]["paid_video_usd"] = quote["estimated_usd"]
    return quote, hero


def render_film(
    run_dir, brief, script, variants, *, paid=False, approved_usd=None, sidecar_url=None
):
    run = Path(run_dir).resolve()
    root = run / "film"
    root.mkdir(parents=True, exist_ok=True)
    upstream = sidecar_url or os.getenv("CLIPFORGE_URL", "http://127.0.0.1:3039")
    try:
        resp = httpx.get(upstream + "/api/health", timeout=2, trust_env=False)
        if resp.status_code != 200:
            upstream = None
    except httpx.HTTPError:
        upstream = None
    drafts = []
    for index, var in enumerate(variants):
        progress(
            f"Preparing draft {index + 1} of {len(variants)} · {var['title']}",
            phase="drafts",
            completed=index,
            total=len(variants),
            unit="drafts ready",
        )
        drafts.append(
            _render(
                run,
                brief,
                var["script"],
                var["id"],
                var["title"],
                var["format"],
                upstream=upstream,
                judge=index == 0,
            )
        )
    if not drafts:
        raise ValueError("Select at least one variant")
    progress(
        "Draft videos are ready",
        phase="drafts",
        completed=len(drafts),
        total=len(drafts),
        unit="drafts ready",
    )
    hero = None
    quote = None
    if paid:
        quote, hero = _hero(run, brief, script, upstream, approved_usd)
    script_hash = hashlib.sha256(
        json.dumps(script, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if not paid and (run / "film.json").is_file():
        previous = json.loads((run / "film.json").read_text())
        if (
            previous.get("script_hash") == script_hash
            and previous.get("hero")
            and safe_file(run, previous["hero"].get("video"))
        ):
            hero, quote = previous["hero"], previous.get("quote")
    chosen = hero or drafts[0]
    if not chosen["exports"] and chosen["gate"]["status"] != "fail":
        chosen["exports"] = {
            k: p.relative_to(run).as_posix()
            for k, p in platform_exports(
                run / chosen["video"], root / chosen["id"]
            ).items()
        }
    result = {
        "script_hash": script_hash,
        "video": chosen["video"],
        "storyboard": chosen["storyboard"],
        "contact_sheet": chosen["contact_sheet"],
        "exports": chosen["exports"],
        "gate": chosen["gate"],
        "qc": chosen["qc"],
        "variants": drafts,
        "hero": hero,
        "recipe": chosen["recipe"],
        "clipforge": chosen["clipforge"],
        "quote": quote,
    }
    if hero and upstream:
        progress("Preparing the storyboard from the finished film", phase="exports")
        try:
            result["director"] = import_verified_board(
                run, brief, script, upstream, hero
            )
        except (httpx.HTTPError, OSError, RuntimeError, ValueError, KeyError) as error:
            result["director"] = {"status": "unavailable", "reason": str(error)[:240]}
    if hero and upstream and hero.get("clipforge", {}).get("project_id"):
        try:
            progress("Creating the film cover and carousel", phase="exports")
            result["social"] = cover_and_carousel(upstream, run, hero, script)
        except (httpx.HTTPError, OSError, ValueError, KeyError) as error:
            result["social"] = {"status": "unavailable", "reason": str(error)[:240]}
    save_json(run / "film.json", result)
    return result
