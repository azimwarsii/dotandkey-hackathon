"""Retrieve dated market evidence, catalog facts and saved campaign destinations."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache, partial
from math import log
from urllib.parse import urlencode

from market_intel.studio import runs

from . import cache, catalog
from .evidence import cards, competitor_cards

IGNORE = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "show",
    "tell",
    "the",
    "to",
    "us",
    "we",
    "what",
    "which",
    "who",
    "why",
    "with",
    "would",
    "find",
    "please",
    "about",
}
TOPICS = {
    "review_share": "share volume",
    "opportunity_score": "score prioritize invest biggest highest investment budget spend ranking",
    "recommendation": "recommendation recommend should action strategy improve next",
    "strength": "strength swot",
    "weakness": "weakness swot",
    "threat": "threat risk swot",
    "opportunity": "opportunity swot",
    "aspect": "sentiment feel customer complaint complain dislike feedback",
    "whitespace": "gap whitespace missing opportunity",
    "category_pain": "pain issue complaint",
    "unmet_needs": "wish request need",
    "launch": "new launch launched recent",
    "competitor": "competitor peer rival competition",
    "forecast": "growth forecast demand projection predict",
    "tracked_term": "trend trending",
    "trend": "trend trending",
    "product": "product sku catalog",
    "campaign": "campaign brief studio",
    "video": "video film reel draft render",
    "kit": "kit download asset artwork listing script",
    "reference": "reference research reel inspiration",
    "review": "review quote",
}


def words(value):
    # Singularize common plurals without changing words such as "glass" or "SPF".
    return {
        w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us")) else w
        for w in re.findall(r"[^\W_]+", (value or "").casefold())
        if w not in IGNORE
    }


def scope(question, default):
    names = cache.categories()
    if default.casefold() not in {c.casefold() for c in names}:
        cache.category_name(default)
    cleaned = question
    found = []
    for name in names:
        pattern = r"\b" + re.escape(name).replace(r"\ ", r"[ -]?") + r"s?\b"
        cleaned, count = re.subn(pattern, " ", cleaned, flags=re.IGNORECASE)
        if count:
            found.append(name)
    return found, cleaned.strip()


def destination(kind, title, category, description, **route):
    href = "/?" + urlencode({"category": category, **route})
    return {
        "id": href,
        "href": href,
        "view": route["view"],
        "title": title,
        "type": kind,
        "category": category,
        "description": description,
    }


@lru_cache(maxsize=48)
def market_index(name, day, signature):
    report = cache.cached_report(name, day)
    return [
        {
            k: row[k]
            for k in ("id", "href", "view", "title", "category", "description", "type")
        }
        for row in (*cards(report), *competitor_cards(report))
    ]


@lru_cache(maxsize=192)
def reference_title(path, modified):
    row = runs.load(path, {})
    return row.get("id"), row.get("title"), row.get("creator")


def workspace_items(products, day):
    by_handle = {p["handle"]: p for p in products}
    for p in products:
        facts = []
        if p["price"] is not None:
            facts.append(f"Catalog price ₹{p['price']:g}")
        if p["size"]:
            facts.append(str(p["size"]))
        if p["hero_ingredient"]:
            facts.append("Featured ingredient " + p["hero_ingredient"])
        yield destination(
            "product",
            p["title"],
            p["category"],
            ". ".join(facts),
            view="products",
            product=p["handle"],
            as_of=str(day),
        )
    for path in sorted(runs.root().glob("*/run.json"), reverse=True):
        meta = runs.load(path, {})
        p = by_handle.get(meta.get("handle"))
        if not p or (meta.get("created_at") or "")[:10] > str(day):
            continue
        title = meta.get("title") or p["title"]
        folder = path.parent
        item = partial(
            destination, category=p["category"], view="studio", run=folder.name
        )
        yield item(
            "campaign",
            title,
            studioStep="overview",
            description="Open the campaign brief in Content Studio.",
        )
        dest = runs.campaign_dir(folder)
        if (dest / "film.json").is_file():
            yield item(
                "video",
                title + " · Video",
                studioStep="video",
                description="A rendered campaign film is available.",
            )
        if (dest / "creative.json").is_file():
            yield item(
                "kit",
                title + " · Campaign kit",
                studioStep="kit",
                description="Download the artwork, copy and available films.",
            )
        for manifest in folder.glob("research/*/post.json"):
            try:
                ident, post, creator = reference_title(
                    manifest, manifest.stat().st_mtime_ns
                )
            except FileNotFoundError:
                continue
            if ident and post:
                yield item(
                    "reference",
                    post,
                    studioStep="inspect",
                    description=title + (" · " + creator if creator else ""),
                    reference=ident,
                )


def review_items(query, names, day):
    if len(query) < 3:
        return []
    placeholders = ",".join("?" for _ in names)
    with cache.database() as db:
        rows = db.execute(
            f"""
            SELECT r.body_hash, r.body, r.source, p.title, p.category, json_extract(p.data,'$.handle') AS handle
            FROM review r JOIN product p USING(product_ref)
            WHERE p.is_competitor=0 AND p.is_combo=0 AND p.category IN ({placeholders})
              AND instr(lower(r.body),lower(?))>0 AND coalesce(date(r.date),'')<=?
              AND coalesce(date(json_extract(r.data,'$.observed_at')),'')<=?
              AND coalesce(date(json_extract(p.data,'$.published_at')),'')<=?
            ORDER BY r.date DESC,r.body_hash LIMIT 3""",
            (*names, query, str(day), str(day), str(day)),
        ).fetchall()
    results = []
    for row in rows:
        r = destination(
            "review",
            row["body"][:220],
            row["category"],
            row["title"] + " · " + row["source"],
            view="products",
            product=row["handle"],
            as_of=str(day),
        )
        r["id"] = "review-" + row["body_hash"]
        r["href"] += "#" + r["id"]
        results.append(r)
    return results


def retrieve(question, default, day, *, workspace=False):
    day = day or cache.latest_day()
    mentioned, query = scope(question, default)
    names = mentioned or [default]
    markets = cache.categories() if workspace and not mentioned else names
    signature = tuple(cache.signature())
    allocation = re.search(
        r"\b(invest|spend|budget|prioriti[sz]e|biggest opportunity|highest opportunity|rank categories)\b",
        question,
        re.IGNORECASE,
    )
    if allocation and not mentioned:
        scored = [
            cache.cached_report(c, day, index_only=True) for c in cache.categories()
        ]
        scored = sorted(
            (r for r in scored if r["opportunity_score"] is not None),
            key=lambda r: -r["opportunity_score"],
        )
        leaders = []
        for summary in scored[:3]:
            card = next(
                r
                for r in market_index(summary["category"], day, signature)
                if r["type"] == "opportunity_score"
            )
            leaders.append(card)
        if leaders:
            return [r["category"] for r in leaders], leaders
    products = catalog.products(None, "", day)["products"]
    candidates = list(workspace_items(products, day))
    for name in markets:
        candidates.extend(market_index(name, day, signature))
    candidates += review_items(query.strip('“”"'), markets, day)
    tokens = words(query or question)
    # Category-only queries also return products and campaigns in that category.
    docs = [
        (
            r,
            words(r["title"]),
            words(r.get("description")),
            words(TOPICS.get(r["type"])),
        )
        for r in candidates
        if not mentioned or r["category"] in mentioned
    ]
    frequency = Counter(
        w for _, title, desc, topics in docs for w in (title | desc | topics) & tokens
    )
    weights = {w: 1 + log((1 + len(docs)) / (1 + frequency[w])) for w in tokens}
    ranked = []
    for row, title, desc, topics in docs:
        matches = tokens & (title | desc | topics)
        if not matches:
            continue
        score = sum(
            weights[w] * (3 if w in title or w in topics else 1) for w in matches
        )
        score *= len(matches) / max(len(tokens), 1)
        if row["category"] in names:
            score *= 1.15
        ranked.append((score, row))
    ranked.sort(key=lambda pair: -pair[0])
    return names, [r for _, r in ranked[:30]]
