"""Reviewable Sarvam translations of locked public copy, with forward/reverse checks."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import time
import unicodedata

import httpx
from dotenv import load_dotenv

from .brief import BANNED, write_json
from .copy import PUBLIC_NEUTRAL


LANGUAGES = {"hi-IN": "Hindi", "hi-Latn": "Hinglish"}
VERSION = 1
MODEL = "mayura:v1"
REVERSE_MODEL = "sarvam-translate:v1"
NUMBER = re.compile(r"\d+(?:[.,]\d+)*\+?\s*%?")
SPF = re.compile(r"(?:\bspf|एस\s*पी\s*एफ|एसपीएफ)\s*[:.\-]?\s*(\d+\s*\+?)", re.I)
PA = re.compile(r"(?:\bPA|पीए)\s*(\+{1,4})", re.I)
BANNED_NEW = re.compile(
    r"\b(?:guarantee[ds]?|clinically proven|permanent(?:ly)?|all.day protection|prevents skin cancer)\b",
    re.I,
)
STOP = set(
    "a an and the it its for in is of on at to with you your more let's lets before from by".split()
)


def _norm(text):
    return " ".join(str(text).casefold().split()).strip(" .!?।")


def _digest(data):
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _numeric(text):
    normalized = "".join(
        str(unicodedata.decimal(c)) if c.isdecimal() else c
        for c in unicodedata.normalize("NFKC", text)
    )
    return Counter(
        x.replace(" ", "").replace(",", "") for x in NUMBER.findall(normalized)
    )


def _review(source, target, reverse):
    hard = []
    notes = []
    if _numeric(source) != _numeric(target) or _numeric(source) != _numeric(reverse):
        hard.append("Numeric value, percentage or qualifier changed.")
    for qualifier, expression in (("SPF", SPF), ("PA", PA)):
        expected = sorted(v.replace(" ", "") for v in expression.findall(source))
        if any(
            expected != sorted(s.replace(" ", "") for s in expression.findall(text))
            for text in [target, reverse]
        ):
            hard.append(f"{qualifier} protection label changed.")
    if (BANNED.search(reverse) or BANNED_NEW.search(reverse)) and not (
        BANNED.search(source) or BANNED_NEW.search(source)
    ):
        hard.append("Backtranslation introduced a restricted claim.")
    negative = r"\b(?:no|zero|non|free|without|doesn.t)\b"
    if bool(re.search(negative, source, re.I)) != bool(
        re.search(negative, reverse, re.I)
    ):
        hard.append("The backtranslation changed the direction of the claim.")
    words = lambda s: {v for v in re.findall(r"[a-z]+", s.casefold()) if v not in STOP}
    a, b = words(source), words(reverse)
    similarity = round(len(a & b) / max(len(a | b), 1), 3)
    if similarity < 0.34:
        notes.append("Review the wording against the backtranslation.")
    return hard, notes, similarity


def _translate(client, text, source, target, *, model, mode, roman=False):
    payload = {
        "input": text,
        "source_language_code": source,
        "target_language_code": target,
        "model": model,
        "mode": mode,
        "numerals_format": "international",
    }
    if roman:
        payload["output_script"] = "roman"
    for attempt in range(3):
        response = client.post("https://api.sarvam.ai/translate", json=payload)
        if response.status_code == 429 and attempt < 2:
            try:
                delay = float(response.headers.get("retry-after", "1"))
            except ValueError:
                delay = 1
            time.sleep(min(max(delay, 1), 8) * (attempt + 1))
            continue
        response.raise_for_status()
        body = response.json()
        translated = body["translated_text"].strip()
        if not translated:
            raise ValueError("Empty translation")
        return translated, body.get("request_id")
    raise RuntimeError("Sarvam translation was rate-limited")


def _source_lines(creative, brief):
    facts = {r["id"]: r["text"] for r in brief["claim_sources"]}
    rows = []

    def add(asset, field, text, refs, locked=False):
        text = str(text).strip()
        if not text:
            return
        if locked:
            valid = True
        elif refs == ["editorial-copy"]:
            valid = _norm(text) in {_norm(v) for v in PUBLIC_NEUTRAL}
        else:
            valid = (
                bool(refs)
                and all(r in facts for r in refs)
                and _norm(text) == _norm(". ".join(facts[r].strip(" .") for r in refs))
            )
        rows.append(
            {
                "id": asset + "." + field,
                "asset_id": asset,
                "field": field,
                "source": text,
                "fact_refs": refs,
                "locked": locked,
                "source_verified": valid,
            }
        )

    for s in creative["script"]["shots"]:
        for k in ["text", "vo"]:
            add(s["id"], k, s[k], [s.get("line_refs", {}).get(k) or s["insight_ref"]])
    for row in creative.get("listings", []):
        refs = row["refs"]
        add(row["id"], "title", row["title"], [refs["title"]])
        for i, bullet in enumerate(row["bullets"]):
            add(row["id"], "bullet-" + str(i + 1), bullet, refs["bullets"][i : i + 1])
        add(row["id"], "description", row["description"], refs["description"])
        # Search terms are indexed marketplace inputs and retain their observed language.
        add(row["id"], "keywords", row["keywords"], [], locked=True)
    return rows


def localize(run_dir, brief, creative, language):
    """Create an adaptation for human review. No mutation to English creative or film."""
    language = {
        "hinglish": "hi-Latn",
        "hi-latn": "hi-Latn",
        "hindi": "hi-IN",
        "hi-in": "hi-IN",
    }.get(str(language).lower(), language)
    if language not in LANGUAGES:
        raise ValueError("Supported locales are hi-IN and hi-Latn.")
    root = Path(run_dir)
    out = root / "locales" / (language + ".json")
    lines = _source_lines(creative, brief)
    mode = "code-mixed" if language == "hi-Latn" else "formal"
    forward_model, reverse_model = (
        (MODEL, REVERSE_MODEL) if language == "hi-Latn" else (REVERSE_MODEL, MODEL)
    )
    signature = {
        "version": VERSION,
        "mode": mode,
        "locale": language,
        "forward_model": forward_model,
        "reverse_model": reverse_model,
    }
    source_hash = _digest([signature, lines])
    previous = {}
    if out.is_file():
        previous = json.loads(out.read_text())
        if previous.get("source_digest") == source_hash and not previous["summary"].get(
            "unavailable"
        ):
            return previous
    load_dotenv()
    key = os.getenv("SARVAM_API_KEY")
    cached = {}
    if previous.get("signature") == signature:
        cached = {
            row["source"]: row
            for row in previous.get("lines", [])
            if row.get("source_verified")
            and row["status"] in {"pending_review", "blocked"}
        }
    unique = sorted(
        {r["source"] for r in lines if not r["locked"] and r["source_verified"]}
    )
    missing = [v for v in unique if v not in cached]
    if missing and not key:
        raise ValueError("SARVAM_API_KEY is required to generate new translations.")
    with httpx.Client(
        headers={"api-subscription-key": key or ""}, timeout=28
    ) as client:

        def translate_pair(text):
            try:
                value, forward_id = _translate(
                    client,
                    text,
                    "en-IN",
                    "hi-IN",
                    model=forward_model,
                    mode=mode,
                    roman=language == "hi-Latn",
                )
                reverse, reverse_id = _translate(
                    client, value, "hi-IN", "en-IN", model=reverse_model, mode="formal"
                )
                errors, notes, score = _review(text, value, reverse)
                if language == "hi-IN" and not re.search(r"[\u0900-\u097f]", value):
                    notes.append(
                        "Source terms remain in Latin script. Verify the intended Hindi wording."
                    )
                return {
                    "translation": None if errors else value,
                    "rejected_candidate": value if errors else None,
                    "backtranslation": reverse,
                    "flags": errors + notes,
                    "similarity": score,
                    "status": "blocked" if errors else "pending_review",
                    "request_ids": [forward_id, reverse_id],
                }
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                detail = (
                    f"HTTP {exc.response.status_code}"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else type(exc).__name__
                )
                return {
                    "translation": None,
                    "backtranslation": None,
                    "flags": ["Sarvam translation unavailable: " + detail],
                    "status": "unavailable",
                    "request_ids": [],
                }

        with ThreadPoolExecutor(max_workers=3) as pool:
            for text, result in zip(missing, pool.map(translate_pair, missing)):
                cached[text] = result
    fields = (
        "translation",
        "backtranslation",
        "rejected_candidate",
        "flags",
        "similarity",
        "status",
        "request_ids",
    )
    for row in lines:
        if not row["source_verified"]:
            row.update(
                status="blocked",
                translation=None,
                backtranslation=None,
                flags=["Source differs from the referenced English fact."],
                request_ids=[],
            )
        elif row["locked"]:
            row.update(
                status="source_preserved",
                translation=row["source"],
                backtranslation=None,
                flags=["Marketplace search terms kept in their original language."],
                request_ids=[],
            )
        else:
            row.update({k: v for k, v in cached[row["source"]].items() if k in fields})
    counts = Counter(r["status"] for r in lines)
    data = {
        "id": "localization-" + language,
        "path": str(out.relative_to(root)),
        "language": language,
        "label": LANGUAGES[language],
        "source_language": "en-IN",
        "source_digest": source_hash,
        "signature": signature,
        "status": "pending_bilingual_review",
        "publishable": False,
        "lines": lines,
        "summary": {
            "total": len(lines),
            "unique_source_lines": len(unique),
            "pending_review": counts["pending_review"],
            "blocked": counts["blocked"],
            "unavailable": counts["unavailable"],
            "source_preserved": counts["source_preserved"],
            "flagged": sum(bool(r["flags"]) for r in lines if not r["locked"]),
        },
        "recipe": {
            "provider": "Sarvam",
            "source": "creative.json",
            "models": [forward_model, reverse_model],
            "mode": mode,
            "script": "Roman" if language == "hi-Latn" else "Devanagari",
            "documentation": "https://docs.sarvam.ai/api-reference/text/translate-text",
            "checks": [
                "English fact reference",
                "numbers, percentages, SPF and PA",
                "restricted claims in backtranslation",
                "lexical drift",
            ],
            "release_gate": "Independent bilingual review required before use in public copy.",
        },
    }
    write_json(out, data)
    return data
