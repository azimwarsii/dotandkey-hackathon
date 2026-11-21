"""Reproduce the blind sampling frame or score the frozen, independently labeled sentences.

Run from the repository root with python -m validation.evaluate_aspects [--sample DB].
Sampling uses broad topic cues, independent of tagger predictions. The frozen
release fixture records the resulting sample, including source and review identity.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from market_intel.aspects import LEXICON_PATH, lexicon, sentences, tag_sentence

DIR = Path(__file__).resolve().parent
FIXTURE = DIR / "aspect_sentences.jsonl"
REPORT = DIR / "aspect_precision.json"
STRATA = {
    "white_cast": r"white\s?cast|whitish|chalky|white layer",
    "greasy_sticky": r"greas|heavy|oily|sticky|lightweight",
    "breakouts": r"acne|breakout|broke me|pimple",
    "irritation": r"irritat|itch|burn|redness|sting",
    "fragrance": r"smell|scen[t]|perfume|fragranc",
    "hydration": r"hydrati|moisturi|plump|dry|suppl",
    "glow_results": r"bright|glow|radiant|luminous",
    "texture": r"texture|creamy|pilling|spread|blend",
    "packaging": r"packaging|cap |pump|bottle|leak",
    "value_price": r"cost|worth|pric[eiy]|expensive|afford",
    "authenticity": r"fake|genuine|original|expired|seal|duplicate",
    "spf_protection": r"protect|sunburn|\btanned\b|uv ray",
    "longevity": r"long.lasting|lasts|reapply|stays|wears off",
    "under_makeup": r"makeup|make.up|foundation",
    "absorption": r"absorb|sink[s]? in",
    "cleansing": r"cleans|residue|dirt",
    "barrier_repair": r"barrier",
    "pigmentation": r"dark spots|pigment|uneven",
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def draw_sample(db):
    unique = {}
    with sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True) as conn:
        for ref, bodyhash, raw in conn.execute("SELECT product_ref,body_hash,data FROM review ORDER BY product_ref,body_hash"):
            data = json.loads(raw)
            for index, sentence in enumerate(sentences(data["body"])):
                if not 5 <= len(sentence.split()) <= 42:
                    continue
                normalized = " ".join(sentence.casefold().split())
                unique.setdefault(normalized, {
                    "id": digest(ref + bodyhash + str(index))[:18], "product_ref": ref,
                    "review_hash": bodyhash, "source": data["source"], "rating": data.get("rating"),
                    "url": data.get("source_url") or data.get("url"), "sentence": sentence,
                })
    remaining = sorted(unique.values(), key=lambda v: digest("dk-aspects-holdout-v1:" + v["id"]))
    selected = []
    for aspect, pattern in STRATA.items():
        chosen = [v for v in remaining if re.search(pattern, v["sentence"], re.I)][:6]
        selected.extend(dict(v, stratum=aspect) for v in chosen)
        ids = {v["id"] for v in chosen}
        remaining = [v for v in remaining if v["id"] not in ids]
    selected.extend(dict(v, stratum="background") for v in remaining[:150-len(selected)])
    return sorted(selected, key=lambda v: digest("display:"+v["id"]))


def evaluate():
    rows = [json.loads(line) for line in FIXTURE.read_text().splitlines()]
    stats = {a: Counter() for a in lexicon()}
    for row in rows:
        truth = row["gold"]
        predicted = tag_sentence(row["sentence"], row["rating"])
        for a in truth.keys() | predicted.keys():
            c = stats[a]
            c["gold"] += int(a in truth)
            c["predicted"] += int(a in predicted)
            c["aspect_correct"] += int(a in truth and a in predicted)
            c["polarity_correct"] += int(a in truth and a in predicted and truth[a] == predicted[a])
    out = {}
    for a, c in stats.items():
        n = c["predicted"]
        precision = c["polarity_correct"] / n if n else None
        out[a] = {"predicted_n": n, "gold_n": c["gold"], "aspect_correct": c["aspect_correct"],
                  "polarity_correct": c["polarity_correct"], "aspect_precision": c["aspect_correct"]/n if n else None,
                  "precision": precision, "enabled": bool(n >= 5 and precision >= .70)}
    return {"sentences": len(rows), "annotator": "Model-reviewed, pending independent human validation",
            "sampling": "Up to 6 cases per broad topic plus a deterministic unfiltered background sample; counts are conditional on this sample.",
            "method": "Exact aspect and sentence polarity, including mixed/neutral. Review rating is hidden from annotation. No holdout tuning.",
            "minimum_predicted_n": 5, "minimum_precision": .7,
            "lexicon_sha256": hashlib.sha256(LEXICON_PATH.read_bytes()).hexdigest(),
            "tagger_sha256": hashlib.sha256((LEXICON_PATH.parents[1]/"market_intel"/"aspects.py").read_bytes()).hexdigest(),
            "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
            "strata": dict(sorted(Counter(v["stratum"] for v in rows).items())), "aspects": out}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", metavar="DB", help="Print the deterministic unlabeled sample from a Part 1 DB")
    args = parser.parse_args()
    if args.sample:
        for row in draw_sample(args.sample):
            print(json.dumps(row, ensure_ascii=False))
    else:
        print(json.dumps(evaluate(), indent=2, ensure_ascii=False))
