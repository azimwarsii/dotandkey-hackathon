"""Match a selected reference video's pacing through the local ClipForge sidecar."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .compose import safe_file
from .providers import save_json

MIME = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}


def _fits_script(shots):
    if not isinstance(shots, list) or not 2 <= len(shots) <= 40:
        return False
    durations = [s.get("duration") for s in shots if isinstance(s, dict)]
    return (
        len(durations) == len(shots)
        and all(
            type(value) in (int, float) and 0.2 <= value <= 45 for value in durations
        )
        and 3 <= sum(durations) <= 120
    )


def match_reference(run_dir, reference, destination, *, sidecar_url=None):
    """Return the reference with the chosen timings and persist the measurement recipe."""
    if not reference:
        return None
    root = Path(run_dir).resolve()
    saved = reference.get("shots") or reference.get("analysis", {}).get("shots") or []
    source = reference.get("media")
    media = safe_file(root, source) if isinstance(source, str) else None
    report = {
        "reference_id": reference.get("id"),
        "url": reference.get("url"),
        "media": source,
        "source": "saved research scene cuts"
        if _fits_script(saved)
        else "default script timing",
        "shots": saved if _fits_script(saved) else [],
        "saved_shots": saved,
    }
    base = (sidecar_url or os.getenv("CLIPFORGE_URL", "http://127.0.0.1:3039")).rstrip(
        "/"
    )
    if not media or media.suffix.lower() not in MIME:
        report["reason"] = "There is no saved reference video for ClipForge to analyze."
    elif media.stat().st_size > 80 * 1024**2:
        report["reason"] = "The reference exceeds ClipForge's 80 MB input limit."
    elif urlsplit(base).hostname not in {"localhost", "127.0.0.1", "::1", "clipforge"}:
        report["reason"] = "Reference analysis requires a local ClipForge endpoint."
    else:
        try:
            with (
                media.open("rb") as stream,
                httpx.Client(base_url=base, timeout=150, trust_env=False) as client,
            ):
                response = client.post(
                    "/api/replicate/analyze",
                    files={"file": (media.name, stream, MIME[media.suffix.lower()])},
                )
                response.raise_for_status()
                result = response.json()
            beats = result.get("generationBeats") or result.get("shots")
            if not _fits_script(beats):
                raise ValueError(
                    "ClipForge found no multi-shot skeleton within the supported script timings."
                )
            report.update(
                source="ClipForge replicate/analyze",
                shots=beats,
                source_cuts=result["shots"],
                duration=result["duration"],
                sidecar_media=result.get("path"),
            )
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as error:
            report["reason"] = str(error)[:250]
    save_json(Path(destination) / "reference-rhythm.json", report)
    return {**reference, "shots": report["shots"], "rhythm": report}
