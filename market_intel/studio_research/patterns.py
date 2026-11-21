"""Group visually inspected posts. One-source directions remain hypotheses."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

import numpy as np


def _signature(post):
    readings = {
        row.get("field"): str(row.get("value", "")).lower()
        for row in post.get("semantic", [])
    }
    words = (
        readings.get("hook", "")
        + " "
        + readings.get("format", "")
        + " "
        + readings.get("portable_brick", "")
    )
    if any(
        token in words
        for token in (
            "documentary",
            "public awareness",
            "public demonstration",
            "uv camera",
            "uv light",
            "field test",
        )
    ):
        hook, style = "demonstration", "documentary"
    elif any(
        token in words
        for token in (
            "chart",
            "problem/solution",
            "checklist",
            "printed sheet",
            "list of",
        )
    ):
        hook, style = "visual guide", "graphic"
    elif any(
        token in words
        for token in ("animated", "animation", "motion graphic", "diagram")
    ):
        hook, style = "animated reveal", "graphic"
    elif any(
        token in words
        for token in (
            "interview",
            "talking head",
            "testimonial",
            "personal experience",
            "personal story",
        )
    ):
        hook, style = "first-person opener", "presenter"
    else:
        hook = "face first" if post.get("face_in_first_second") else "visual opener"
        style = post.get("media_type", "video")
    d = post.get("duration")
    length = (
        "slides"
        if d is None
        else "≤15s"
        if d <= 15
        else "15–35s"
        if d <= 35
        else ">35s"
    )
    rate = post.get("cuts_per_second")
    pacing = (
        "still"
        if rate is None
        else "continuous"
        if rate < 0.1
        else "measured"
        if rate < 0.5
        else "fast"
    )
    text = post.get("first_text_at")
    return (
        hook,
        style,
        length,
        pacing,
        "immediate text" if text is not None and text <= 1 else "later or absent text",
    )


def _measured(group, field):
    return [p[field] for p in group if p.get(field) is not None]


def pattern_board(posts):
    groups = defaultdict(dict)
    for p in posts:
        if p.get("status") == "ready" and p.get("frames"):
            groups[_signature(p)][p["id"]] = p
    patterns = []
    names = {
        "demonstration": "Show the demonstration early",
        "animated reveal": "Animate the ingredient reveal",
        "visual guide": "Match concerns to a visual guide",
        "first-person opener": "Open with a personal experience",
        "face first": "Lead with a face",
        "visual opener": "Lead with a visual detail",
    }
    for signature, members in groups.items():
        group = sorted(
            members.values(), key=lambda p: (-(p.get("outlier_ratio") or 0), p["id"])
        )
        lead = group[0]
        ratios = [
            i["outlier_ratio"] for i in group if i.get("outlier_ratio") is not None
        ]
        creators = {p["creator"] for p in group if p.get("creator")}
        winners = [p for p in group if p.get("evidence") == "outlier-backed"]
        measurements = winners or group
        durations = _measured(measurements, "duration")
        first_text = _measured(measurements, "first_text_at")
        cuts = _measured(measurements, "cuts_per_second")
        title = names[signature[0]]
        patterns.append(
            {
                "id": "pattern-" + lead["id"],
                "name": title,
                "title": title,
                "post_ids": [p["id"] for p in group],
                "thumbnails": [p["thumbnail"] for p in group],
                "urls": [p.get("url") for p in group],
                "repeatability": len(creators),
                "n": len(group),
                "breakout_post_count": len(winners),
                "median_outlier_ratio": median(ratios) if ratios else None,
                "signature": list(signature),
                "evidence": "replicated breakout"
                if len({p["creator"] for p in winners if p.get("creator")}) >= 2
                else "single-account breakout"
                if winners
                else "curated hypothesis",
                "brand_fit": "Test the filming mechanic using claims from the selected product brief.",
                "winning_spec": {
                    "hook_max_s": 1.5,
                    "product_by_s": 3,
                    "text_by_s": 1,
                    "length_iqr": [
                        round(float(x), 2) for x in np.percentile(durations, [25, 75])
                    ]
                    if durations
                    else [],
                    "duration_median_s": median(durations) if durations else None,
                    "cuts_per_second_median": median(cuts) if cuts else None,
                    "observed_first_text_median_s": median(first_text)
                    if first_text
                    else None,
                    "observed_face_in_first_second_share": round(
                        sum(bool(p.get("face_in_first_second")) for p in measurements)
                        / len(measurements),
                        3,
                    ),
                    "measurement_n": len(measurements),
                    "target_basis": "Hook, product and overlay deadlines are studio pre-flight targets. IQR and pacing are measured on cited references.",
                },
                "recipe": "creator-breakout-kit breakout-pattern-research. Deterministic grouping on hook, visual format, length, pacing and text timing.",
            }
        )
    return sorted(
        patterns,
        key=lambda p: (-p["repeatability"], -(p["median_outlier_ratio"] or 0), p["id"]),
    )
