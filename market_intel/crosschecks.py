"""Attach cited Crustdata AI brand overlaps to already ranked competitors."""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlsplit


def _text(value):
    normalized = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in normalized if not unicodedata.combining(c))))


def _has_brand(brand, text):
    name = _text(brand)
    normalized = " " + _text(text) + " "
    aliases = {
        "l oreal paris": ("loreal paris",), "the plant fix plix": ("plix",),
        "lakme": ("lakme",), "pond s": ("ponds",), "dr sheth s": ("dr sheths",),
        "drveda": ("dr veda",), "true frog": ("truefrog",),
    }
    return any(" " + alias + " " in normalized for alias in (name, *aliases.get(name, ())))


def cited_brand_matches(brand, query, observed_at, results):
    """Only link provider references explicitly naming the candidate in their returned text."""
    evidence = {}
    for result in results:
        if result.get("source") != "ai" or not isinstance(result.get("references"), list):
            continue
        content = str(result.get("content") or "")
        mentioned = _has_brand(brand, content)
        for reference in result["references"]:
            if not isinstance(reference, dict):
                continue
            url = str(reference.get("url") or "")
            parsed = urlsplit(url)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname:
                continue
            title = str(reference.get("title") or "")
            snippet = str(reference.get("snippet") or "")
            if not _has_brand(brand, title + " " + snippet):
                continue
            evidence[url] = {"url":url, "title":title, "snippet":snippet, "source":"crustdata_ai_reference",
                             "query":query, "observed_at":observed_at, "answer_mentions_brand":mentioned,
                             "scope":"brand_overlap_in_cited_reference"}
    return list(evidence.values())


def apply_crosscheck(store, category, query, observed_at, results):
    """Atomic JSON-field changes preserve ranks, scores and other workers' annotations."""
    matches = 0
    with store.db:
        for row in store.db.execute("""SELECT c.product_ref,p.brand FROM competitor_set AS c
                                    JOIN product AS p USING(product_ref) WHERE c.category=? ORDER BY c.rank""",(category,)).fetchall():
            evidence = cited_brand_matches(row["brand"], query, observed_at, results)
            if evidence:
                store.db.execute("""UPDATE competitor_set SET reasons=json_set(reasons,'$.ai_crosscheck',json(?))
                                 WHERE category=? AND product_ref=?""",
                                 (json.dumps(evidence,ensure_ascii=False),category,row["product_ref"]))
                matches += 1
    return matches
