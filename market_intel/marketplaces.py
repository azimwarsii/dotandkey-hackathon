"""Discover and refresh product-specific marketplace listings."""
from __future__ import annotations

import csv
import re
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from itertools import islice
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from rapidfuzz import fuzz
from selectolax.lexbor import LexborHTMLParser

from .client import SourceUnavailable
from .marketplace_parsers import parse_listing, parse_snippet

DOMAINS = {"amazon": "amazon.in", "flipkart": "flipkart.com", "nykaa": "nykaa.com"}
SPIKE_URLS = {
    "amazon": "https://www.amazon.in/dp/B0DVLMD36J",
    "flipkart": "https://www.flipkart.com/dot-key-sunscreen-spf-50-pa-watermelon-cooling-sunscreen-in-vivo-tested-hyaluronic/p/itm1aa93a315ff03?pid=SNRGWTFHWCT8GHCK",
    "nykaa": "https://www.nykaa.com/dot-key-watermelon-hyaluronic-cooling-sunscreen-spf-50-pa/p/14072071?skuId=8938307",
}
SPIKE_URLS["flipkart_reviews"] = SPIKE_URLS["flipkart"].replace("/p/", "/product-reviews/")
MATCH_THRESHOLD = 0.72
STOPWORDS = set("for of with to and all a the in vivo tested new age uv filters spf pa skin oily dry daily radiant face".split())
FORMATS = {"stick", "mist", "spray", "tinted", "mineral", "body", "combo", "refill"}
SIZE_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(ml|millilit(?:er|re)s?|g|gms?|grams?|kg|l|pairs?|patch(?:es)?)\b", re.I)


def canonical_listing(market, url):
    """Keep variant identifiers while dropping affiliate and tracking parameters."""
    parts = urlsplit(url)
    domain = DOMAINS[market]
    if parts.scheme not in {"http", "https"} or parts.hostname not in (domain, "www." + domain, "m." + domain):
        return None
    params = parse_qs(parts.query)
    if market == "amazon":
        match = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:/|$)", parts.path, re.I)
        if match:
            asin = match[1].upper()
            return asin, "https://www.amazon.in/dp/" + asin
    elif market == "flipkart":
        item = re.search(r"/p/(itm[a-zA-Z0-9]+)(?:/|$)", parts.path)
        if item:
            pid = params.get("pid", [""])[0].upper()
            if pid and not re.fullmatch(r"[A-Z0-9]+", pid):
                return None
            query = urlencode({"pid": pid}) if pid else ""
            return pid or item[1], urlunsplit(("https", "www.flipkart.com", parts.path.rstrip("/"), query, ""))
    else:
        item = re.search(r"/p/(\d+)(?:/|$)", parts.path)
        if item:
            sku = params.get("skuId", [""])[0]
            if sku and not sku.isdigit():
                return None
            query = urlencode({"skuId": sku}) if sku else ""
            return sku or item[1], urlunsplit(("https", "www.nykaa.com", parts.path.rstrip("/"), query, ""))
    return None


def _words(value):
    s = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z]+|\d+", s.replace("moisturiser", "moisturizer"))


def _sizes(text):
    sizes = set()
    for amount, unit in SIZE_RE.findall(str(text)):
        value = float(amount)
        if unit.lower() in {"kg", "l"}:
            value *= 1000
        if unit.lower().startswith("pair"):
            sizes.add((value * 2, "patches"))
        elif unit.lower().startswith("patch"):
            sizes.add((value, "patches"))
        else:
            sizes.add((value, "ml" if unit.lower().startswith(("m", "l")) else "g"))
    return sizes


def _primary_variant(product):
    variants = product.get("variants") or []
    return next((v for v in variants if v.get("available")), variants[0] if variants else {})


MULTIPACK = re.compile(r"\b(?:pack|set)\s*(?:of\s*)?(?:[2-9]|[1-9]\d+)\b|\b(?:duo|bundle|twin pack|multipack)\b"
                       r"|(?:g(?:m|rams?)?|ml|kg|l)\s*[x×*]\s*(?:[2-9]|[1-9]\d+)\b"
                       r"|\b(?:[2-9]|[1-9]\d+)\s*[x×*]\s*\d+\s*(?:g|ml|kg|l)", re.I)
# Repeated product forms in an '&'/'+' title commonly indicate two different
# items. An ingredient blend such as 'Vitamin C + E' has only one product form.
PRODUCT_FORM = re.compile(r"body lotion|sunscreen|cleanser|face\s*wash|moisturi[sz]er|face serum|lip balm|shampoo|conditioner", re.I)


def _is_bundle(title):
    packages = {size for size in _sizes(title) if size[1] != "patches"}
    if MULTIPACK.search(title) or len(packages) > 1:
        return True
    return bool(re.search(r"(?:" + PRODUCT_FORM.pattern + r")\s*(?:\d+\s*(?:ml|g))?\s*[+&]\s*"
                          r"[^|,+&]{0,55}?(?:" + PRODUCT_FORM.pattern + r")", title, re.I))


def _size_evidence(row):
    # Unit-price denominators on Amazon ('₹168 /100 g') describe a comparison
    # price, not the package size being sold.
    snippet = row.get("snippet") or ""
    before_price = re.split(r"₹|price, product page|M\.R\.P", snippet, maxsplit=1, flags=re.I)[0]
    if row.get("market") == "amazon" and snippet:
        return row["title"] + " " + before_price
    return row["title"] + " " + str(row.get("size") or before_price)


def _confidence(product, row):
    brand = set(_words(product.get("brand") or "Dot & Key")) - {"and"}
    title = product["title"]
    result = row["title"]
    candidate = set(_words(result))
    if not brand.issubset(candidate | set(_words(row.get("brand")))):
        return 0
    source_words = set(_words(title))
    if (source_words & FORMATS) != (candidate & FORMATS):
        return 0
    if _is_bundle(result):
        return 0
    size = _sizes(product.get("size") or title)
    other = _sizes(_size_evidence(row))
    if size:
        units = {unit for _, unit in size}
        if size != {quantity for quantity in other if quantity[1] in units}:
            return 0
    if product["product_ref"].startswith("competitor:") and not size:
        return 0  # A second marketplace cannot corroborate an unknown base pack size.
    distinctive = ("gentle skin cleanser", "hair mask", "conditioner", "shampoo", "intense", "micellar",
                   "watermelon", "cica", "mango", "pomegranate", "strawberry", "dragon fruit", "plushie", "meltie")
    identity = " " + " ".join(_words(title)) + " "
    matched = " " + " ".join(_words(result)) + " "
    if any(f" {term} " in identity and f" {term} " not in matched for term in distinctive):
        return 0
    if "gel" in source_words and "sorbet" in candidate and "gel" not in candidate:
        return 0
    spf = re.search(r"spf\s*(\d+)", title, re.I)
    result_spf = re.search(r"spf\s*(\d+)", result, re.I)
    if spf and result_spf and spf[1] != result_spf[1]:
        return 0
    # When the primary variant is a shade, require its descriptive name in the result.
    variant = str(_primary_variant(product).get("title") or "")
    if variant and not _sizes(variant) and variant.lower() != "default title":
        shade = re.split(r"\s+-\s+|\b(?:high|medium|low) tinted\b", variant, maxsplit=1, flags=re.I)[0]
        if not set(_words(shade)).issubset(candidate):
            return 0
    source = source_words - brand - STOPWORDS
    identifying = {s for s in source if not s.isdigit()} - FORMATS - set(_words(product.get("category"))) - {"sunscreen", "cream", "gel", "serum", "ml", "g"}
    if identifying and len(identifying & candidate) < max(1, len(identifying) * 0.45):
        return 0
    overlap = len(source & candidate) / max(1, len(source))
    fuzzy = fuzz.token_set_ratio(" ".join(sorted(source)), " ".join(sorted(candidate - STOPWORDS))) / 100
    return round(0.5 * overlap + 0.35 * fuzzy + 0.15 * (1 if size and other else 0.65), 3)


@lru_cache(maxsize=256)
def _direct_rows(client, query, market):
    if market == "nykaa":
        return []  # Public search is JS-rendered. Manual overrides can still be refreshed.
    from .competitors import parse_category_page
    if market == "amazon":
        url = "https://www.amazon.in/s?" + urlencode({"k": query})
    else:
        url = "https://www.flipkart.com/search?" + urlencode({"q": query})
    pages = client.enrich([url])
    return parse_category_page(pages[url], market, url) if pages.get(url) else []


def load_overrides(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"product_ref", "market", "url"}.issubset(reader.fieldnames or []):
            raise ValueError("Override CSV requires product_ref,market,url")
        overrides = {}
        for row in reader:
            key = row["product_ref"], row["market"]
            if key in overrides or key[1] not in DOMAINS or not canonical_listing(key[1], row["url"]):
                raise ValueError(f"Invalid or duplicate listing override at line {reader.line_num}")
            overrides[key] = row if row.get("variant_sku") else row["url"]
        return overrides


DEFAULT_OVERRIDES = load_overrides(Path(__file__).with_name("listing_overrides.csv"))


def discover(client, product, market, overrides=None):
    if product.get("is_combo"):
        return None
    if isinstance(overrides, (str, Path)):
        overrides = load_overrides(overrides)
    key = (product["product_ref"], market)
    override = (overrides or {}).get(key, DEFAULT_OVERRIDES.get(key))
    if isinstance(override, dict):
        primary = _primary_variant(product)
        url = override["url"] if primary.get("sku") == override["variant_sku"] else None
    else:
        url = override
    if url:
        canonical = canonical_listing(market, url)
        if not canonical:
            raise ValueError(f"Invalid {market} override for {key[0]}")
        listing = dict(product_ref=key[0], market=market, external_id=canonical[0], url=canonical[1],
                       title=product["title"], confidence=1.0, match_method="manual",
                       matched_variant_sku=_primary_variant(product).get("sku"))
        if isinstance(override, dict) and override.get("verification_url"):
            listing.update(verification_url=override["verification_url"], verification_note=override.get("verification_note"))
        if getattr(client, "has_crustdata", True) is False and product.get("category"):
            cards = _direct_rows(client, f"{product['brand']} {product['category']}", market)
            card = next((row for row in cards if row["external_id"] == canonical[0]), None)
            if card:
                listing.update(snippet=card["snippet"], source_url=card["source_url"], card_price=card.get("price"),
                               discovered_at=client.observations.get(card["source_url"]))
        return listing
    brand = product.get("brand") or "Dot & Key"
    variant = product.get("size") or _primary_variant(product).get("title")
    query = " ".join(str(part) for part in [brand, product["title"], variant] if part and part != "Default Title")
    if getattr(client, "has_crustdata", True):
        return _best_match(client, product, market, client.search(query, site=DOMAINS[market]), "web_search")
    rows = _direct_rows(client, f"{brand} {product['category']}", market)
    listing = _best_match(client, product, market, rows, "marketplace_search")
    if listing or market == "nykaa":
        return listing
    rows = _direct_rows(client, query, market)
    return _best_match(client, product, market, rows, "marketplace_product_search")


def _best_match(client, product, market, rows, method):
    best = None
    for row in rows:
        canonical = canonical_listing(market, row.get("url") or "")
        if not canonical or not row.get("title"):
            continue
        confidence = _confidence(product, dict(row, market=market))
        if confidence < MATCH_THRESHOLD or (best and confidence <= best["confidence"]):
            continue
        best = dict(product_ref=product["product_ref"], market=market, external_id=canonical[0], url=canonical[1],
                    confidence=confidence, title=row["title"], snippet=row.get("snippet"), match_method=method,
                    brand=row.get("brand"), size=row.get("size"))
        if method.startswith("marketplace_") and row.get("price") and row.get("source_url"):
            best["card_price"] = row["price"]
        best["discovered_at"] = getattr(client, "observations", {}).get(row.get("source_url") or "/web/search/live") or datetime.now(timezone.utc).isoformat()
        if row.get("source_url"):
            best["source_url"] = row["source_url"]
    return best


def listing_match_is_valid(product, listing):
    """Re-evaluate a saved match from the original card evidence, including older records."""
    market = listing["market"]
    identity = canonical_listing(market, listing.get("url") or "")
    if not identity or identity[0] != listing.get("external_id") or listing["product_ref"] != product["product_ref"]:
        return False
    if listing.get("match_method") == "manual":
        sku = listing.get("matched_variant_sku")
        return not sku or sku == _primary_variant(product).get("sku")
    if identity == canonical_listing(market, product.get("url") or ""):
        return True  # The selected competitor's original marketplace listing.
    row = dict(listing)
    if not row.get("brand"):
        brand = product.get("brand") or "Dot & Key"
        normalized = " ".join(_words(row.get("snippet")))
        candidate = " ".join(_words(row["title"]))
        if (" ".join(_words(brand)) + " " + candidate[:45]) in normalized or normalized.startswith(" ".join(_words(brand)) + " "):
            row["brand"] = brand
    return _confidence(product, row) >= MATCH_THRESHOLD


def resolve_listing_conflicts(listings):
    """Give an external variant to its best-supported product in this category."""
    by_id = {}
    for listing in listings:
        key = listing["market"], listing["external_id"]
        by_id.setdefault(key, []).append(listing)
    winners = []
    for candidates in by_id.values():
        def priority(row):
            verified = row.get("match_method") == "manual" or row.get("match_method") is None
            return verified, row["confidence"]
        best = max(priority(row) for row in candidates)
        strongest = [row for row in candidates if priority(row) == best]
        if len({row["product_ref"] for row in strongest}) == 1:
            winners.append(strongest[0])
    return winners


def search_price_snapshot(listing):
    """Return a separately dated card observation when its source and selling price are known."""
    price = listing.get("card_price")
    source = listing.get("source_url")
    stamp = listing.get("discovered_at")
    if source and stamp and type(price) in (float, int) and price > 0:
        return dict(price=price, source="marketplace_search_card", url=source, captured_at=stamp)
    return None


def _blocked(html):
    if not html or not html.strip():
        return True
    top = html[:6000].lower()
    return any(marker in top for marker in ("robot check", "<title>access denied", "validatecaptcha",
                                            "<title>captcha", "<title>just a moment", "enter the characters you see below"))


def _review_url(listing, page):
    p = urlsplit(listing["url"])
    query = parse_qs(p.query)
    query["page"] = [str(page)]
    return urlunsplit((p.scheme, p.netloc, p.path.replace("/p/", "/product-reviews/"), urlencode(query, doseq=True), ""))


def _batches(items):
    it = iter(items)
    while True:
        batch = list(islice(it, 10))
        if not batch:
            return
        yield batch


def _fetch(client, urls, parse):
    """Retry unavailable or unparseable pages once with the provider's human mode."""
    pages = client.enrich(urls)
    parsed = {}
    failed = []
    for url in urls:
        html = pages.get(url, "")
        data = None if _blocked(html) else parse(url, html)
        if data:
            parsed[url] = data
        else:
            failed.append(url)
    if failed and getattr(client, "has_crustdata", True):
        try:
            retry = client.enrich(failed, human_mode=True)
        except SourceUnavailable as exc:
            if "HTTP 403" not in str(exc):
                raise
            retry = {}
        for url in failed:
            html = retry.get(url) or ""
            if not _blocked(html):
                pages[url] = html
                data = parse(url, html)
                if data:
                    parsed[url] = data
    return pages, parsed


def _page_metrics(client, html):
    if _blocked(html):
        return {}
    tree = LexborHTMLParser(html)
    tree.strip_tags(["script", "style", "noscript", "nav", "footer", "aside"])
    text = " ".join(tree.root.text(separator=" ").split())[:16000]
    fields = ("price", "mrp", "rating", "rating_count", "review_count")
    schema = {"type": "object", "description": "Extract only this main product's explicitly stated INR prices, ratings and counts. Omit unknown values.",
              "properties": {k: {"type": "integer" if k.endswith("count") else "number", "minimum": 0} for k in fields},
              "additionalProperties": False}
    schema["properties"]["rating"]["maximum"] = 5
    extracted = client.extract(schema, text) if text else {}
    return {k: v for k,v in extracted.items() if k in fields and type(v) in (int, float) and v >= 0
            and (k != "rating" or v <= 5) and (not k.endswith("count") or isinstance(v, int))}


def _dedupe(reviews):
    merged = {}
    for review in reviews:
        key = " ".join(review["body"].casefold().split())
        if key not in merged:
            merged[key] = review
        else:
            for field, value in review.items():
                if merged[key].get(field) is None:
                    merged[key][field] = value
    return list(merged.values())


def collect_listings(client, listings, review_pages=2):
    """Yield one observation per supplied listing, batching up to ten URLs per request."""
    if review_pages < 0 or review_pages > 5:
        raise ValueError("review_pages must be between 0 and 5")
    for batch in _batches(listings):
        by_url = {item["url"]: item for item in batch}
        def parse(url, html):
            item = by_url[url]
            snapshot, reviews = parse_listing(item["market"], html, item["product_ref"])
            return (snapshot, reviews) if snapshot or reviews else None
        pages, parsed = _fetch(client, list(by_url), parse)
        reviews_for = {url: [] for url in by_url}
        review_tasks = {_review_url(item, n): item for item in by_url.values() if item["market"] == "flipkart"
                        for n in range(1, review_pages + 1)}
        def parse_reviews(url, html):
            return parse_listing("flipkart", html, review_tasks[url]["product_ref"])[1]
        for urls in _batches(review_tasks):
            _, review_data = _fetch(client, urls, parse_reviews)
            for url, reviews in review_data.items():
                reviews_for[review_tasks[url]["url"]].extend(dict(r, url=url) for r in reviews)
        for listing in batch:
            url = listing["url"]
            snapshot, reviews = parsed.get(url, ({}, []))
            reviews = _dedupe([dict(r, url=url) for r in reviews] + reviews_for[url])
            source = "pdp"
            if any(key not in snapshot for key in ("price", "rating", "rating_count")) and getattr(client, "has_extractor", True):
                extra = _page_metrics(client, pages.get(url, ""))
                extra = {key: value for key, value in extra.items() if key not in snapshot}
                if extra:
                    source = "pdp" if snapshot else "llm_pdp"
                    snapshot = dict(snapshot, **extra, llm_fields=sorted(extra))
            evidence_url = url
            observations = getattr(client, "observations", {})
            stamp = observations.get(url)
            if not snapshot:
                snapshot = parse_snippet(listing.get("snippet") or "")
                source = "search_snippet"
                evidence_url = listing.get("source_url") or url
                stamp = listing.get("discovered_at") or observations.get(evidence_url)
            if snapshot:
                snapshot = dict(snapshot, source=source, url=evidence_url,
                                captured_at=stamp or datetime.now(timezone.utc).isoformat())
            yield listing, snapshot or None, [
                dict(r, product_ref=listing["product_ref"], observed_at=observations.get(r.get("url")))
                for r in reviews]
            if snapshot and snapshot.get("price") is None:
                card = search_price_snapshot(listing)
                if card and card["captured_at"] != snapshot["captured_at"]:
                    yield listing, card, []
