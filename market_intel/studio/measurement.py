"""Measure produced files against their reference spec; retain the exact sampled frames."""

import json
import re
from hashlib import sha256

from .runs import load, write_json


def _visible_text(line, observed):
    clean = lambda text: re.sub(r"[^\w]", "", str(text).casefold())
    return bool(clean(line)) and clean(line) in clean(observed)


def measure(run, result, script, pattern, brief):
    import cv2
    from PIL import Image

    from market_intel.studio_research.media import (
        _frame,
        _pack_reference,
        shot_times,
        video_info,
    )

    video = run / result["video"]
    dest = video.parent / "measured"
    dest.mkdir(exist_ok=True)
    spec = (pattern or {}).get("winning_spec", {})
    guard = result.get("gate", {}).get("claim_guard", {})
    digest = sha256(video.read_bytes())
    digest.update(
        json.dumps(["v2", script["shots"], spec, guard], sort_keys=True).encode()
    )
    fingerprint = digest.hexdigest()
    saved = load(dest / "preflight.json", {})
    if saved.get("fingerprint") == fingerprint:
        return saved
    duration, _ = video_info(video)
    cuts = shot_times(video, duration)
    photo = brief["product"].get("cutout") or next(
        iter(brief["product"].get("local_images", [])), ""
    )
    ref = _pack_reference(run / photo) if photo else None
    first, last = script["shots"][0], script["shots"][-1]
    times = {t for t in (0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0) if t < duration}
    times.update(
        min(s["start"] + min(0.25, s["duration"] / 2), duration - 0.05)
        for s in script["shots"]
    )
    times.add(max(0, duration - min(0.5, last["duration"] / 2)))
    cap = cv2.VideoCapture(str(video))
    evidence = []
    try:
        for t in sorted(times):
            cap.set(cv2.CAP_PROP_POS_MSEC, 1000 * t)
            ok, image = cap.read()
            if ok:
                evidence.append(
                    _frame(
                        Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)),
                        t,
                        dest.relative_to(run).as_posix(),
                        dest,
                        ref,
                        t <= 3,
                        t in cuts,
                        True,
                    )
                )
    finally:
        cap.release()
    rows = []

    def check(key, label, value, passed, frame=None, shot=first):
        rows.append(
            {
                "id": key,
                "label": label,
                "value": value,
                "status": "warn" if passed is None else "pass" if passed else "fail",
                "shot_ref": shot["id"],
                "time": frame["time"] if frame else shot["start"],
                "frame": frame["path"] if frame else None,
            }
        )

    hook = next((f for f in evidence if _visible_text(first["text"], f["ocr"])), None)
    pack = next((f for f in evidence if f["product_match"]), None)
    cta = next(
        (f for f in reversed(evidence) if _visible_text(last["text"], f["ocr"])), None
    )
    for key, label, frame, limit in (
        ("hook", "Opening hook visible", hook, 1.5),
        ("product", "Catalog pack visible", pack, 3),
        ("overlay", "Opening overlay readable", hook, 1),
    ):
        check(
            key,
            label,
            frame["time"] if frame else "Unconfirmed in sampled frames",
            frame["time"] <= limit if frame else None,
            frame,
        )
    iqr = spec.get("length_iqr") or []
    check(
        "duration",
        "Runtime within reference IQR",
        duration,
        iqr[0] <= duration <= iqr[1] if len(iqr) == 2 else None,
    )
    pace = (len(cuts) - 1) / duration if duration > 0 else 0
    target = spec.get("cuts_per_second_median")
    check(
        "pace",
        "Measured cut rate within 25% of reference",
        round(pace, 3),
        abs(pace - target) <= max(0.05, 0.25 * target)
        if isinstance(target, (int, float))
        else None,
    )
    check(
        "cta",
        "Closing CTA visible",
        cta["ocr"] if cta else "Unconfirmed in sampled frames",
        True if cta else None,
        cta,
        last,
    )
    check(
        "claims",
        "Scripted overlays and VO passed claim guard",
        guard.get("status"),
        guard["status"] == "pass" if "status" in guard else None,
    )
    scoreable = [r for r in rows if r["status"] != "warn"]
    measured = {
        "fingerprint": fingerprint,
        "video": result["video"],
        "pattern_id": (pattern or {}).get("id"),
        "checks": rows,
        "score": round(
            100 * sum(r["status"] == "pass" for r in scoreable) / len(scoreable)
        )
        if scoreable
        else None,
        "measured": len(scoreable),
        "total": len(rows),
        "cuts": cuts,
        "reference_spec": spec,
        "method": "OCR for scripted overlays and CTA; ORB catalog pack matching; FFmpeg scene differences above 0.30. Unconfirmed readings are marked for review.",
        "samples": [
            {k: f[k] for k in ("time", "path", "product_match", "ocr")}
            for f in evidence
        ],
    }
    write_json(dest / "preflight.json", measured)
    return measured


def measure_campaign(run, film, creative, patterns, brief):
    scripts = {v["id"]: v["script"] for v in creative["variants"]}
    for variant in [*film["variants"], *([film["hero"]] if film.get("hero") else [])]:
        script = scripts.get(variant["id"], creative["script"])
        pattern_id = script["shots"][0].get("pattern_ref")
        pattern = next((p for p in patterns if p["id"] == pattern_id), None)
        variant["measured_preflight"] = measure(run, variant, script, pattern, brief)
    return film
