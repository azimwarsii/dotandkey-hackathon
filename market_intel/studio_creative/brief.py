"""Build a product-level fact sheet, preserving the boundary between catalog copy and research."""

from __future__ import annotations

import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image, ImageOps
from selectolax.lexbor import LexborHTMLParser

from ..insights import build_insights
from ..metrics import utc_date
from ..store import Store


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, encoding="utf8"
    ) as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    os.replace(f.name, path)


def get_official(url):
    allowed = {"www.dotandkey.com", "dotandkey.com", "cdn.shopify.com"}
    for _ in range(4):
        if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in allowed:
            raise ValueError(
                "The asset URL must belong to the official Shopify storefront."
            )
        response = httpx.get(url, timeout=22)
        if response.is_redirect:
            url = urljoin(url, response.headers["location"])
            continue
        response.raise_for_status()
        return response.content
    raise ValueError("Too many redirects on the official asset")


BANNED = re.compile(
    r"\b(?:fairness|whitening|cures?|treats?|chemical[ -]free|100\s*%\s*safe|no\.?\s*1\b|dermatologist[ -]recommended)\b",
    re.I,
)
SKIP = re.compile(
    r"\b(?:subjects|study|self.assessment|pregnan|clinically|proven|guarantee|best|always|trial|percent|tested on|doctor|dermatolog|FDA|clinical|100%|agreed|reported)\b|\*",
    re.I,
)


def _fact_rows(product):
    url = product["url"]
    rows = []

    def add(text, field, kind):
        if not isinstance(text, str):
            return
        text = " ".join(text.split()).strip(" .,-")
        if not text or BANNED.search(text) or text in {r["text"] for r in rows}:
            return
        if any(
            i != (product.get("spf") or "")
            for i in re.findall(r"\bSPF\s*(\d+\+?)", text, re.I)
        ):
            return
        identifier = sha256((product["handle"] + kind + text).encode()).hexdigest()[:12]
        rows.append(
            {
                "id": "fact-" + identifier,
                "text": text,
                "field": field,
                "kind": kind,
                "url": url,
            }
        )

    add(product["title"], "title", "name")
    name = re.split(
        r"\s+(?:IN[- ]VIVO|In.Vivo|with|For|SPF|PA[+])\b",
        product["title"],
        maxsplit=1,
        flags=re.I,
    )[0]
    add(name, "title", "short_name")
    if product.get("spf"):
        add("SPF " + product["spf"], "spf", "spf")
    add(product.get("size"), "size", "size")
    add(product.get("hero_ingredient"), "hero_ingredient", "ingredient")
    for ingredient in product.get("ingredients", []):
        add(ingredient, "ingredients", "ingredient")
    description = product.get("description", "")
    # Product pages append comparison tables, routines and FAQs about other products.
    intro = re.split(
        r"\b(?:Tried\. Tested|Suggested Routine|Ingredients List|Q\.|Results In|Why You|How to use|Active Ingredients)\b",
        description,
        flags=re.I,
    )[0][:800]
    for sentence in re.split(r"(?<=[.!?])\s+|\s*[|•]\s*", intro):
        if (
            15 <= len(sentence) <= 145
            and not sentence.endswith("melon")
            and not SKIP.search(sentence)
        ):
            add(sentence, "description", "benefit")
    for phrase in (
        "instant cooling",
        "oil-free hydration",
        "zero white cast",
        "non-oily finish",
        "aqua gel",
        "lightweight",
        "quick-absorbing",
        "fragrance-free",
        "hyaluronic acid",
        "ceramides",
    ):
        match = re.search(r"\b" + re.escape(phrase) + r"\b", intro, re.I)
        if match:
            add(match[0], "description", "feature")
    instructions = description.split("Suggested Routine")[0].split("Q.")[0]
    for match in re.finditer(
        r"(?:^|(?<=[.!?])\s+|\s)(Use |Apply |Re-apply |Reapply |Massage |Rinse |Shake )([^.!?]{5,90})(?=[.!?])",
        instructions,
    ):
        if not SKIP.search(match[0]):
            add(match[0], "description", "direction")
    return rows


def _brand(product, root):
    kit = {
        "colors": ["#191919", "#ffffff"],
        "fonts": ["sans-serif"],
        "font_files": [],
        "logo": None,
        "tone_words": [],
        "do_not_say": [
            "fairness",
            "whitening",
            "chemical-free",
            "100% safe",
            "No.1",
            "dermatologist recommended",
        ],
        "source": product["url"],
        "status": "unavailable",
        "palette_evidence": {},
    }
    try:
        html = get_official(product["url"]).decode("utf8", "replace")
        tree = LexborHTMLParser(html)
        colors = []
        for var, val in re.findall(
            r"(--(?:pdp-(?:primary|second|third)-color|color-(?:primary|foreground|background)))\s*:\s*(#[0-9a-fA-F]{6}|\d+\s+\d+\s+\d+)\s*[;\n]",
            html,
        ):
            if not val.startswith("#"):
                val = "#%02x%02x%02x" % tuple(map(int, val.split()))
            kit["palette_evidence"][var] = val
        palette = kit["palette_evidence"]
        for var in (
            "--pdp-primary-color",
            "--pdp-second-color",
            "--pdp-third-color",
            "--color-foreground",
            "--color-background",
        ):
            if palette.get(var) and palette[var] not in colors:
                colors.append(palette[var])
        if colors:
            kit["colors"] = colors
        for img in tree.css("img"):
            if img.attributes.get("alt", "").strip().lower() != "dot & key":
                continue
            url = urljoin(product["url"], img.attributes.get("src") or "")
            ext = Path(urlsplit(url).path).suffix.lower()
            if ext not in (".svg", ".png", ".jpg", ".webp"):
                continue
            path = "inputs/logo" + ext
            (root / path).write_bytes(get_official(url))
            kit.update(logo=path, logo_source=url)
            break
        for node in tree.css('link[as="font"]'):
            url = urljoin(product["url"], node.attributes.get("href") or "")
            name = Path(urlsplit(url).path).name
            if re.fullmatch(r"Poppins-(?:Regular|Bold|Medium)\.woff2?", name):
                path = "inputs/" + name
                (root / path).write_bytes(get_official(url))
                kit["font_files"].append(
                    {
                        "path": path,
                        "url": url,
                        "weight": 700
                        if "Bold" in name
                        else 500
                        if "Medium" in name
                        else 400,
                    }
                )
        if kit["font_files"]:
            kit["fonts"] = ["Poppins"]
        kit["status"] = "observed"
    except (ValueError, httpx.HTTPError, OSError):
        kit["status"] = "partial" if kit["logo"] else "unavailable"
    kit["tone_words"] = [
        w
        for w in (
            "cooling",
            "glow",
            "gentle",
            "fresh",
            "lightweight",
            "hydrating",
            "smooth",
        )
        if re.search(r"\b" + w + r"\b", product.get("description", ""), re.I)
    ]
    return kit


def build_brief(handle, db_path, catalog_path, run_dir, *, as_of=None):
    root = Path(run_dir)
    (root / "inputs").mkdir(parents=True, exist_ok=True)
    with closing(Store(db_path)) as store:
        catalog = [
            p
            for p in store.catalog()
            if not as_of
            or not utc_date(p.get("published_at"))
            or utc_date(p["published_at"]) <= as_of
        ]
        product = next(
            (p for p in catalog if p["handle"] == handle and not p.get("is_combo")),
            None,
        )
        if not product:
            raise ValueError("Unknown single-product handle")
        raw = store.report(product["category"])
    result = build_insights(db_path, catalog_path, product["category"], as_of)
    if as_of:
        raw["reviews"] = [
            r
            for r in raw["reviews"]
            if all(
                not utc_date(r.get(k)) or utc_date(r[k]) <= as_of
                for k in ("date", "observed_at")
            )
        ]
    props = {
        k: product.get(k)
        for k in (
            "product_ref",
            "handle",
            "title",
            "price",
            "currency",
            "size",
            "ingredients",
            "hero_ingredient",
            "spf",
            "images",
            "url",
            "category",
            "skin_type",
            "brand",
        )
    }
    props["local_images"] = []
    prior = root / "inputs/image-sources.json"
    try:
        previous = {item["path"]: item["url"] for item in json.loads(prior.read_text())}
    except (OSError, ValueError, KeyError):
        previous = {}

    def image_asset(item):
        i, url = item
        dest = f"inputs/product-{i + 1:02}.jpg"
        try:
            if not (root / dest).exists() or previous.get(dest) != url:
                data = get_official(url)
                im = ImageOps.exif_transpose(Image.open(BytesIO(data))).convert("RGB")
                im.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
                im.save(root / dest, quality=89)
            return {"path": dest, "url": url}
        except (httpx.HTTPError, ValueError, OSError):
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        images = [r for r in pool.map(image_asset, enumerate(props["images"])) if r]
    write_json(prior, images)
    props["local_images"] = [r["path"] for r in images]
    props["image_sources"] = images
    facts = _fact_rows(product)
    swot = result["swot"]
    competitors = [
        p
        for p in raw["products"]
        if p.get("is_competitor") or p["brand"].casefold() != "dot & key"
    ]
    reviews = [
        r
        for r in raw["reviews"]
        if r["product_ref"] == product["product_ref"] and r.get("body")
    ]

    def sample_reviews(test, rows, scope):
        return [
            {
                "id": "review-" + sha256(r["body"].encode()).hexdigest()[:12],
                "quote": r["body"][:220],
                "rating": r["rating"],
                "source": r.get("source_url") or r.get("url"),
                "product_ref": r["product_ref"],
                "scope": scope,
                "platform": r.get("source"),
            }
            for r in sorted(
                rows, key=lambda v: (v.get("date") or "", v["body"]), reverse=True
            )
            if r.get("body") and r.get("rating") is not None and test(r["rating"])
        ][:4]

    ownrange = [
        {k: p.get(k) for k in ("handle", "title", "size", "spf", "url", "price")}
        for p in catalog
        if p["category"] == product["category"]
        and p["handle"] != handle
        and not p.get("is_combo")
    ][:3]
    peers = [p.get("brand") for p in competitors]
    brief = {
        "id": "brief-" + handle,
        "product": props,
        "allowed_claims": [r["text"] for r in facts],
        "claim_sources": facts,
        "audience": {
            "skin_types": product.get("skin_type", []),
            "age_band": None,
            "language": ["en", "hinglish"],
            "top_desires": sample_reviews(
                lambda stars: stars >= 4, reviews, "selected product"
            ),
            "top_objections": sample_reviews(
                lambda stars: stars <= 2, reviews, "selected product"
            ),
            "category_objections": sample_reviews(
                lambda stars: stars <= 2, raw["reviews"], "category research"
            ),
        },
        "strengths": swot["strength"],
        "weaknesses_to_avoid_in_messaging": swot["weakness"],
        "competitor_weaknesses": [
            r
            for r in swot["opportunity"]
            if r["rule"] in ("peer_pain", "messaging_advantage")
        ],
        "competitors": list(dict.fromkeys(peers)),
        "trends": result["trends"]["trending"],
        "gaps": result["gaps"]["whitespace"][:5],
        "search_terms": list(
            dict.fromkeys(
                [
                    product["category"],
                    product.get("hero_ingredient") or product["category"],
                ]
            )
        ),
        "range": ownrange,
        "brand_kit": _brand(product, root),
        "as_of": result["as_of"],
        "scope": "Catalog facts authorize external copy. Review excerpts and category comparisons are internal creative inputs.",
    }
    write_json(root / "brief.json", brief)
    return brief
