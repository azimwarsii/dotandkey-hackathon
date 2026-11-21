"""Discover and score marketplace competitors using attributable observations."""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode, urljoin, urlsplit
from xml.etree import ElementTree

from selectolax.lexbor import LexborHTMLParser

from .marketplace_parsers import json_product
from .crosschecks import cited_brand_matches
from .marketplaces import canonical_listing

logger = logging.getLogger(__name__)

BRAND_DOMAINS = {
    "Minimalist": "beminimalist.co", "The Derma Co": "thedermaco.com",
    "Deconstruct": "thedeconstruct.in", "Foxtale": "foxtale.in",
    "Plum": "plumgoodness.com", "Re'equil": "reequil.com",
    "Pilgrim": "discoverpilgrim.com", "Aqualogica": "aqualogica.in",
    "Mamaearth": "mamaearth.in", "Lakmé": "lakmeindia.com",
    "Neutrogena": "neutrogena.in", "Cetaphil": "cetaphil.in",
}
SEED_BRANDS = frozenset(BRAND_DOMAINS)
# Additional official sites for observed competitors; seed validation stays independent.
SIGNAL_DOMAINS = {"dr sheth s": "www.drsheths.com", "dermdoc": "buydermdoc.com",
                  "mcaffeine": "www.mcaffeine.com", "nivea": "www.nivea.in"}
SIGNAL_DOMAINS.update({
    "bare anatomy": "innovist.com", "chemist at play": "innovist.com", "clayco": "clayco.in",
    "dermatouch": "dermatouch.com", "dove": "dove.com", "drveda": "drveda.in", "fixderma": "fixderma.com",
    "garnier men": "garnier.in", "joy": "joypersonalcare.com", "l oreal paris": "lorealparis.co.in",
    "pond s": "ponds.in", "parachute advansed": "parachuteadvansed.com", "renee": "reneecosmetics.in",
    "tresemme": "tresemme.com", "true frog": "truefrog.in", "the ordinary": "theordinary.com",
    "the plant fix plix": "plixlife.com", "wishcare": "mywishcare.com",
})
# A fallback company's own metrics have a broader population than the Indian brand.
COMPANY_FALLBACKS = {
    "cetaphil": ("cetaphil.com", "us_brand", "https://www.cetaphil.com/"),
    "dermdoc": ("purplle.com", "parent_company", "https://www.purplle.com/brand/dermdoc"),
    "dove": ("unilever.com", "parent_company", "https://www.unilever.com/brands/"),
    "l oreal paris": ("loreal.com", "parent_company", "https://www.loreal.com/en/consumer-products-division/loreal-paris/"),
    "neutrogena": ("neutrogena.com", "us_brand", "https://www.neutrogena.com/skin"),
    "pond s": ("unilever.com", "parent_company", "https://www.unilever.com/brands/beauty-wellbeing/"),
    "parachute advansed": ("marico.com", "parent_company", "https://marico.com/media_pdf/Parachute_Advansed_Body_Lotion_-_Butter_Smooth.pdf"),
}
MARKETS = {"amazon": "www.amazon.in", "flipkart": "www.flipkart.com"}
# Marketplace queries and title anchors for identifying products in that category.
CATEGORIES = {
    "sunscreen": ("sunscreen SPF 50", r"sunscreen|sun\s*screen|sun\s*block"),
    "moisturiser": ("face moisturiser", r"moisturi[sz]er|moisturi[sz]ing cream|face cream|day cream"),
    "face wash": ("face wash cleanser", r"face\s*wash|facial cleanser|face cleanser|cleanser"),
    "serum": ("face serum", r"(?:face )?serum"),
    "lip balm": ("lip balm", r"lip\s*balm|lip butter|lip treatment"),
    "toner": ("face toner", r"(?:face |facial )?toner"),
    "mask": ("clay face mask skincare", r"(?:face|facial|clay|sheet|mud|peel[ -]off)\s*mask"),
    "eye care": ("under eye cream", r"under[ -]?eye|eye cream|eye gel|eye serum|eye mask"),
    "body": ("body lotion", r"body\s*(?:lotion|wash|cream|scrub|butter|care|sunscreen)"),
    "hair": ("hair mask conditioner", r"hair[ -]*(?:mask|conditioner)|conditioner"),
}
ALIASES = {"bodycare": "body", "body care": "body", "haircare": "hair",
           "hair care": "hair", "eye": "eye care", "moisturizer": "moisturiser"}
PACK = re.compile(r"\b(?:combo|bundle|gift set|duo|pack of\s*(?:[2-9]|\d\d+))\b", re.I)
BUNDLE_QUANTITIES = re.compile(r"\b\d+(?:\.\d+)?\s*(?:g|ml|gm)\s*(?:\+|&|and)\s*.{1,110}?\b\d+(?:\.\d+)?\s*(?:g|ml|gm)\b", re.I)
SIZE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:ml|g|gm|grams?|kg|litres?)\b", re.I)
COUNT = re.compile(r"([\d,]+(?:\.\d+)?\s*[kKmM]?)\s*(?:ratings?|global ratings?)\b", re.I)
PRICE = re.compile(r"(?:₹|\bINR\b|\bRs\.?)\s*([\d,]+(?:\.\d+)?)", re.I)


def _words(value):
    plain = "".join(c for c in unicodedata.normalize("NFKD", str(value or "")).lower()
                    if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def _brand(value):
    key = _words(value).replace(" ", "")
    if key in {"dotkey", "dotandkey"}:
        return "Dot & Key"
    for name in BRAND_DOMAINS:
        if key == _words(name).replace(" ", ""):
            return name
    return (value or "").strip()


def _category(category):
    name = _words(category)
    return CATEGORIES.get(ALIASES.get(name, name), (category, re.escape(name)))


def _brand_for(row):
    title = row["title"]
    tokens = f" {_words(title)} "
    brand = _brand(row.get("brand"))
    if brand:
        return brand
    # Seed brands validate an observed product. A seed on its own never creates one.
    for name in ["Dot & Key", "Dot and Key", *BRAND_DOMAINS]:
        if tokens.startswith(" " + _words(name) + " "):
            return _brand(name)
    # Product names can place a collection between the brand and category
    # ("ClayCo. Purifying Matcha Clay Mask"). Resolve unknowns from the PDP.
    return None


def _number(value):
    if value is None:
        return None
    match = re.fullmatch(r"([\d,.]+)\s*([km]?)", str(value).strip(), re.I)
    if not match:
        return None
    try:
        return float(match[1].replace(",", "")) * {"": 1, "k": 1000, "m": 1000000}[match[2].lower()]
    except ValueError:
        return None


def _text(node):
    return node.text(separator=" ", strip=True) if node else ""


def _structured_list(doc):
    for script in doc.css('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.text())
        except (ValueError, TypeError):
            continue
        entries = [value] if isinstance(value, dict) else value
        if not isinstance(entries, list):
            continue
        for obj in entries:
            if not isinstance(obj, dict):
                continue
            for entry in obj.get("itemListElement") or []:
                if not isinstance(entry, dict):
                    continue
                product = entry.get("item", entry)
                if not isinstance(product, dict):
                    continue
                brand = product.get("brand")
                offers = product.get("offers") or {}
                rating = product.get("aggregateRating") or {}
                yield {"title": product.get("name"), "url": product.get("url"),
                       "brand": brand.get("name") if isinstance(brand, dict) else brand,
                       "rating_count": _number(rating.get("ratingCount")) if isinstance(rating, dict) else None,
                       "price": _number(offers.get("price")) if isinstance(offers, dict) else None}


def parse_category_page(html, market, page_url):
    """Return attributable product cards in display order, preserving absent fields."""
    doc = LexborHTMLParser(html or "")
    rows = {}

    def add(row):
        if not row.get("url") or not row.get("title"):
            return
        ident = canonical_listing(market, urljoin(page_url, row["url"]))
        if not ident:
            return
        external_id, url = ident
        if external_id in rows:
            for key in ("brand", "rating_count", "price"):
                if rows[external_id].get(key) is None and row.get(key) is not None:
                    rows[external_id][key] = row[key]
            return
        rows[external_id] = {**row, "url": url, "external_id": external_id,
                             "market": market, "source_url": page_url, "position": len(rows) + 1}

    selector = '[data-asin]:not([data-asin=""])' if market == "amazon" else "[data-id]"
    for card in doc.css(selector):
        brand = None
        if market == "amazon":
            headings = card.css("h2")
            title_node = card.css_first("a[href] h2, h2 a[href]") or (headings[-1] if headings else None)
            if len(headings) > 1 and title_node and _text(headings[0]) != _text(title_node):
                brand = _text(headings[0])
            asin = card.attributes.get("data-asin", "")
            url = f"https://www.amazon.in/dp/{asin}" if re.fullmatch(r"[A-Z0-9]{10}", asin) else ""
        else:
            title_node = card.css_first("a[title]")
            url = ""
        title = (title_node.attributes.get("title") or _text(title_node)) if title_node else ""
        if not title:
            img = card.css_first("img[alt]")
            title = img.attributes.get("alt", "") if img else ""
        if not url:
            for link in card.css("a[href]"):
                if canonical_listing(market, urljoin(page_url, link.attributes["href"])):
                    url = link.attributes["href"]
                    break
        if not url:
            continue
        snippet = _text(card)
        # Amazon often omits the currency symbol from the displayed price text.
        price_node = card.css_first(".a-price .a-offscreen") if market == "amazon" else None
        price = PRICE.search(_text(price_node) or snippet)
        count = COUNT.search(snippet)
        if not count:
            count = re.search(r"\(\s*([\d,]+(?:\.\d+)?[kKmM]?)\s*\)", snippet)
        if not count and market == "amazon":
            for label in card.css("[aria-label]"):
                count = COUNT.search(label.attributes.get("aria-label", ""))
                if count:
                    break
        size = SIZE.search(title) or SIZE.search(re.split(r"₹|\b(?:price|MRP|INR)\b|M\.R\.P", snippet, maxsplit=1, flags=re.I)[0])
        add({"title": title, "url": url, "brand": brand, "snippet": snippet,
             "price": _number(price[1]) if price else None,
             "rating_count": int(_number(count[1])) if count and _number(count[1]) is not None else None,
             "size": size[0] if size else None})
    for row in _structured_list(doc):
        add(row)
    return list(rows.values())


def _page_url(market, query, page, newest):
    if market == "amazon":
        params = {"k": query, "page": page}
        if newest:
            params["s"] = "date-desc-rank"
        return f"https://{MARKETS[market]}/s?" + urlencode(params)
    params = {"q": query, "page": page}
    if newest:
        params["sort"] = "recency_desc"
    return f"https://{MARKETS[market]}/search?" + urlencode(params)


def _optional(call, default, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except (RuntimeError, OSError, ValueError) as exc:
        logger.warning("%s unavailable: %s", call.__name__, exc)
        return default


def search_rows(client, category, market, newest=False):
    query = _category(category)[0]
    urls = [_page_url(market, query, page, newest) for page in ([1] if newest else [1, 2])]
    pages = _optional(client.enrich, {}, urls)
    rows = []
    seen = set()
    for page, url in enumerate(urls, 1):
        cards = parse_category_page(pages.get(url, ""), market, url)
        # Keep second-page positions behind first-page positions even if it was blocked.
        offset = 0 if page == 1 else len(rows) or (40 if market == "flipkart" else 48)
        for card in cards:
            if card["external_id"] not in seen:
                seen.add(card["external_id"])
                rows.append({**card, "position": offset + card["position"],
                             "source": "marketplace_search", "page": page,
                             "discovered_at": getattr(client, "observations", {}).get(url)})
    if not rows and not newest and getattr(client, "has_crustdata", True):
        results = _optional(client.search, [], query, site=MARKETS[market].removeprefix("www."),
                            sources=["web"], page=2)
        for index, result in enumerate(results, 1):
            ident = canonical_listing(market, result.get("url", ""))
            if not ident or ident[0] in seen or not result.get("title"):
                continue
            seen.add(ident[0])
            snippet = result.get("snippet") or ""
            price, count = PRICE.search(snippet), COUNT.search(snippet)
            rows.append({**result, "external_id": ident[0], "url": ident[1], "market": market,
                         "position": index, "source": "crustdata_web_search",
                         "discovered_at": getattr(client, "observations", {}).get("/web/search/live"),
                         "source_url": result["url"], "snippet": snippet,
                         "price": _number(price[1]) if price else None,
                         "rating_count": _number(count[1]) if count else None})
    return rows


def _claims(product):
    values = []
    for key in ("ingredients", "concerns", "claims", "hero_ingredient"):
        value = product.get(key) or []
        values.extend(value if isinstance(value, (list, tuple)) else [value])
    text = _words(" ".join(str(v) for v in [product.get("title", ""), *values]))
    claims = {_words(v) for v in values if _words(v)}
    claims.update(re.findall(r"\b(?:spf\s*\d+|vitamin\s+[a-z]\d?|oil free|fragrance free|"
                             r"water resistant|matte|tinted|ceramide|niacinamide|hyaluronic acid)\b", text))
    return claims


def _overlap(row, profiles):
    text = f" {_words(row['title'] + ' ' + (row.get('snippet') or ''))} "
    best, matched = 0.0, []
    for claims in profiles:
        hits = sorted(c for c in claims if f" {c} " in text)
        value = len(hits) / len(claims) if claims else 0.0
        if value > best:
            best, matched = value, hits
    return best, matched


def _crosschecks(client, query):
    if not getattr(client, "has_crustdata", True):
        return []
    return _optional(client.search, [], query, sources=["ai"])


def _product_brand(html, market):
    doc = LexborHTMLParser(html or "")
    value = json_product(doc).get("brand")
    if isinstance(value, dict):
        value = value.get("name")
    if not value and market == "amazon":
        byline = _text(doc.css_first("#bylineInfo"))
        match = re.fullmatch(r"(?:Visit the (.+?) Store|Brand:\s*(.+))", byline, re.I)
        if match:
            value = match[1] or match[2]
    return _brand(value) if isinstance(value, str) else None


NET_QUANTITY = re.compile(r"\bnet quantity\s*:?\s*(\d+(?:\.\d+)?)\s*(millilit(?:er|re)s?|ml|grams?|gm|g)\b", re.I)


def net_quantity(html, url, captured_at=None):
    doc = LexborHTMLParser(html or "")
    doc.strip_tags(["script", "style"])
    visible = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", doc.text(separator=" ", strip=True))
    matches = list(NET_QUANTITY.finditer(" ".join(visible.split())))
    quantities = {f"{float(m[1]):g} {'ml' if m[2].lower().startswith('m') else 'g'}" for m in matches}
    if len(quantities) != 1:
        return None
    return quantities.pop(), {"field": "Net Quantity", "excerpt": matches[0][0], "url": url,
                              "captured_at": captured_at}


def _selected_size(html, market):
    doc = LexborHTMLParser(html or "")
    if market == "amazon":
        node = doc.css_first("#variation_size_name .selection, #inline-twister-expanded-dimension-text-size_name")
        text = _text(node)
    else:
        text = ""
        for label in doc.css("div"):
            if label.text(deep=False, strip=True).casefold() in {"selected quantity:", "selected size:"} and label.next:
                text = _text(label.next)
                break
    if not text:
        primary = json_product(doc)
        text = primary.get("size") or primary.get("name") or ""
    size = SIZE.search(text) if isinstance(text, str) else None
    return size[0] if size else None


def select_competitors(client, category, products):
    """Return up to five observed competing products, ranked once per distinct brand."""
    targets = [p for p in products if _category(p.get("category", "")) == _category(category)
               and not p.get("is_combo") and _brand(p.get("brand") or "Dot & Key") == "Dot & Key"]
    if not targets:
        return []
    profiles = [_claims(p) for p in targets]
    prices = [_number(p.get("price")) for p in targets]
    prices = [p for p in prices if p is not None and p > 0]
    rows = []
    for market in MARKETS:
        for row in search_rows(client, category, market):
            title = row["title"]
            if PACK.search(title) or BUNDLE_QUANTITIES.search(title) or not re.search(_category(category)[1], title, re.I):
                continue
            brand = _brand_for(row)
            if brand != "Dot & Key":
                rows.append({**row, "brand": brand})
    if not rows:
        return []
    max_count = max(math.log1p(r.get("rating_count") or 0) for r in rows)
    ai_query = f"Top skincare brands competing with Dot & Key in {category} in India"
    ai_checks = _crosschecks(client, ai_query)
    ai_date = getattr(client, "observations", {}).get("/web/search/live")
    scored = []
    for row in rows:
        count, price, position = row.get("rating_count"), row.get("price"), row["position"]
        price_overlap = 0.0
        if price and prices:
            price_overlap = min(1.0, price / min(prices), max(prices) / price)
        claim_score, matched = _overlap(row, profiles)
        components = {"rating_count": math.log1p(count or 0) / max_count if max_count else 0.0,
                      "rank_position": 1.0 / math.log2(1 + position),
                      "price_band_overlap": price_overlap, "claim_overlap": claim_score}
        weights = {"rating_count": 0.35, "rank_position": 0.25, "price_band_overlap": 0.2, "claim_overlap": 0.2}
        score = sum(components[k] * weights[k] for k in weights)
        ref = f"competitor:{_words(category).replace(' ', '-')}:{row['market']}:{row['external_id']}"
        product = {"product_ref": ref, "title": row["title"], "brand": row["brand"],
                   "category": category, "is_combo": False, "price": price, "size": row.get("size"),
                   "url": row["url"]}
        listing = {k: row[k] for k in ("external_id", "market", "url", "title")}
        listing.update(product_ref=ref, confidence=1.0, snippet=row.get("snippet") or "",
                       source_url=row["source_url"], discovered_at=row.get("discovered_at"))
        reasons = {"source": row["source"], "source_url": row["source_url"], "listing_url": row["url"],
                   "position": position, "rating_count": count, "price": price,
                   "target_price_band": [min(prices), max(prices)] if prices else None,
                   "matched_claims": matched, "components": components, "weights": weights,
                   "brand_source": row["source_url"]}
        scored.append((product, listing, score, reasons))
    winners, brands = [], set()
    ranked = sorted(scored, key=lambda e: (-e[2], e[3]["position"], e[0]["product_ref"]))
    # Identify unlabelled candidates in score order from the PDP itself. Once
    # five brands are confirmed, lower-ranked candidates cannot enter the set.
    pending = {}
    for i, entry in enumerate(ranked):
        product, listing, _, reasons = entry
        brand = product["brand"]
        if not brand:
            if listing["url"] not in pending:
                batch = [r[1] for r in ranked[i:] if not r[0]["brand"]][:5]
                pages = _optional(client.enrich, {}, [item["url"] for item in batch])
                for item in batch:
                    pending[item["url"]] = _product_brand(pages.get(item["url"]), item["market"])
            brand = pending[listing["url"]]
            reasons["brand_source"] = listing["url"]
        if not brand or brand == "Dot & Key":
            continue
        key = _words(brand).replace(" ", "")
        if key not in brands:
            product["brand"] = brand
            reasons.update(seed_brand=brand in SEED_BRANDS, ai_crosscheck=cited_brand_matches(brand, ai_query, ai_date, ai_checks))
            winners.append(entry)
            brands.add(key)
        if len(winners) == 5:
            break
    # These winners' PDPs also feed the snapshot stage through the shared
    # URL cache. Reading selected quantity here makes cross-market matching safe.
    if winners:
        pages = _optional(client.enrich, {}, [listing["url"] for _, listing, _, _ in winners])
        for p, listing, _, _ in winners:
            url = listing["url"]
            html = pages.get(url)
            quantity = net_quantity(html, url, getattr(client, "observations", {}).get(url))
            if quantity:
                p["size"], p["size_source"] = quantity
                listing.update(size=p["size"], size_source=p["size_source"])
            elif not p["size"]:
                p["size"] = _selected_size(html, listing["market"])
    arrivals = {name: [] for name in brands}
    for market in MARKETS:
        for row in search_rows(client, category, market, newest=True):
            brand = _brand_for(row)
            if not brand:
                title_words = " " + _words(row["title"]) + " "
                brand = next((p["brand"] for p, _, _, _ in winners
                              if title_words.startswith(" " + _words(p["brand"]) + " ")), None)
            key = _words(brand).replace(" ", "")
            if key in brands and re.search(_category(category)[1], row["title"], re.I):
                arrivals[key].append({"brand": brand, "category": category, "title": row["title"],
                                      "url": row["url"], "source": market, "source_url": row["source_url"],
                                      "event_type": "marketplace_new_arrival", "date": None})
    for product, _, _, reasons in winners:
        reasons["new_arrivals"] = arrivals[_words(product["brand"]).replace(" ", "")]
    return winners


def _domain_for(client, brand):
    known = BRAND_DOMAINS.get(brand) or SIGNAL_DOMAINS.get(_words(brand))
    if known:
        return known
    hits = _optional(client.search, [], f'"{brand}" official skincare website India')
    # Only accept a domain that names the brand and a result title naming it.
    key = _words(brand).replace(" ", "")
    for hit in hits:
        url = urlsplit(hit.get("url") or "")
        host = (url.hostname or "").removeprefix("www.")
        if url.scheme in {"http", "https"} and key == host.split(".")[0].replace("-", ""):
            if f" {_words(brand)} " in f" {_words(hit.get('title'))} ":
                return host
    return None


def _published(value):
    if isinstance(value, (float, int)):
        try:
            return datetime.fromtimestamp(value, timezone.utc).date()
        except (OverflowError, ValueError, OSError):
            return None
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        try:
            return parsedate_to_datetime(str(value)).date()
        except (TypeError, ValueError, OverflowError):
            return None


def _rss_news(client, brand):
    url = "https://news.google.com/rss/search?" + urlencode({
        "q": f'"{brand}" skincare launch when:90d', "hl": "en-IN", "gl": "IN", "ceid": "IN:en"})
    xml = _optional(client.get, "", url)
    try:
        channel = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []
    return [{"url": item.findtext("link"), "title": item.findtext("title"),
             "date": item.findtext("pubDate"), "publisher": item.findtext("source"),
             "source": "google_news_rss"}
            for item in channel.findall("./channel/item")]


def matches_news_brand(brand, title, snippet=""):
    """Check that a headline refers to the cosmetics brand, including common-word names."""
    title = title.rsplit(" - ", 1)[0]
    text = f"{title} {snippet}"
    content = " " + _words(text) + " "
    if f" {_words(brand)} " not in content:
        return False
    if _words(brand) == "dove" and " dove cameron " in content:
        return False
    if _words(brand) == "joy":
        return bool(re.search(r"\bjoy (?:personal care|skin(?:care)?|beauty|body lotion|face wash)\b", content))
    if _words(brand) not in {"plum", "minimalist", "pilgrim", "deconstruct", "simple", "dove"}:
        return True
    # E.g. "this minimalist beauty brand" uses the word as an adjective.
    if not re.search(r"\b(?:" + re.escape(brand.title()) + r"|" + re.escape(brand.upper()) + r")\b", text):
        return False
    return bool(re.search(r"\b(?:skin(?:care)?|beauty|cosmetics?|moisturi[sz]er|serums?|sunscreens?|"
                          r"makeup|haircare|personal care|shampoo|cleansers?|toners?|lip balm|face wash)\b", content))


def _storefront_signal(client, brand, domain, cutoff, today):
    # Shopify's publication timestamp records an online store event. It does
    # not establish a product's commercial launch date or total brand sales.
    query = urlencode({"limit": 50, "order": "published_at desc"})
    url = f"https://{domain}/products.json?{query}"
    raw = _optional(client.get, "", url)
    try:
        products = json.loads(raw).get("products")
    except (TypeError, ValueError, AttributeError):
        return None
    if not products or not isinstance(products, list):
        return None
    publications = []
    for item in products:
        if not isinstance(item, dict):
            continue
        published = _published(item.get("published_at"))
        handle = item.get("handle") or ""
        if published and cutoff <= published <= today and item.get("title") and re.fullmatch(r"[\w-]+", handle):
            publications.append({"id": item.get("id"), "title": item["title"], "published_at": item["published_at"],
                                 "url": f"https://{domain}/products/{handle}"})
    if not publications:
        return None
    return {"brand": brand, "domain": domain, "source": "shopify_storefront", "source_url": url,
            "captured_at": getattr(client, "observations", {}).get(url),
            "window_start": cutoff.isoformat(), "sample_size": len(products),
            "recent_storefront_publications": publications}


COMPANY_FIELDS = {
    "basic_info": ("name", "primary_domain", "website", "year_founded", "company_type", "employee_count_range", "status"),
    "followers": ("count", "qoq_percent", "mom_percent", "yoy_percent", "six_months_growth_percent", "timeseries"),
    "headcount": ("total", "timeseries", "growth_percent", "growth_absolute", "by_role_absolute", "by_region_absolute"),
    "hiring": ("openings_count", "openings_growth_percent", "by_function_qoq_pct", "by_function_6m_pct"),
    "funding": ("total_investment_usd", "last_round_amount_usd", "last_fundraise_date", "last_round_type", "num_funding_rounds"),
    "competitors": ("paid_seo", "organic_seo"),
    "seo": ("monthly_organic_clicks", "total_organic_results", "average_seo_organic_rank", "monthly_paid_clicks",
            "monthly_google_ads_budget", "monthly_organic_value"),
    "public_launches": ("producthunt_url", "rating", "num_upvotes", "num_reviews", "last_updated"),
}


def _host(value):
    return (urlsplit("//" + str(value or "").split("://")[-1]).hostname or "").lower().removeprefix("www.")


def _company_signal(data, brand, domain, stamp):
    if not data:
        return None
    basic = data.get("basic_info") or {}
    reported = {h for value in [basic.get("primary_domain"), basic.get("website"), *(basic.get("all_domains") or [])]
                if (h := _host(value))}
    wanted = _host(domain)
    if reported and wanted not in reported:
        return None
    name = basic.get("name") or brand
    scope = "brand"
    if wanted == "innovist.com" or _words(name) in {"unilever", "rsh global", "marico limited"}:
        scope = "parent_company"
    elif _words(brand) == "garnier men":
        scope = "brand_family"
    record = {"brand": brand, "domain": domain, "source": "crustdata_company", "captured_at": stamp,
              "source_url": "https://api.crustdata.com/company/enrich",
              "entity_name": name, "entity_scope": scope}
    for group, keys in COMPANY_FIELDS.items():
        source = data.get(group)
        if isinstance(source, dict):
            values = {k: source[k] for k in keys if source.get(k) is not None}
            if values:
                record[group] = values
        elif group == "headcount" and group in data:
            record[group] = None
    traffic = data.get("web_traffic") or {}
    if isinstance(traffic, dict):
        selected = {k: traffic[k] for k in ("quarterly_growth", "qoq_percent") if traffic.get(k) is not None}
        traffic_fields = ("domain", "monthly_visitors", "mom_pct", "qoq_pct", "source_search_pct",
                          "source_direct_pct", "source_social_pct", "monthly_visitors_timeseries")
        for key, values in (traffic.get("domain_traffic") or {}).items():
            if _host(key) == wanted and isinstance(values, dict):
                selected["domain_traffic"] = {wanted: {k: values[k] for k in traffic_fields if values.get(k) is not None}}
        if selected:
            record["web_traffic"] = selected
    return record


def _relevant_news(hits, brand, cutoff, today):
    news, seen = [], set()
    for hit in hits:
        title, url = hit.get("title") or "", hit.get("url") or ""
        content = _words(title + " " + (hit.get("snippet") or ""))
        if url in seen or not title or urlsplit(url).scheme not in {"https", "http"}:
            continue
        if not matches_news_brand(brand, title, hit.get("snippet") or ""):
            continue
        when = _published(hit.get("published_at") or hit.get("published_date") or
                          hit.get("date") or hit.get("timestamp"))
        if when and not cutoff <= when <= today:
            continue
        seen.add(url)
        event_type = "launch_mention" if re.search(
            r"\b(?:launch(?:es|ed|ing)?|unveils?|debuts?|introduc(?:es|ed))\b", content) else "brand_news"
        news.append({"url": url, "title": title, "brand": brand,
                     "date": when.isoformat() if when else None, "event_type": event_type,
                     "publisher": hit.get("publisher"), "snippet": hit.get("snippet") or "",
                     "source": hit.get("source") or "crustdata_news"})
    return news


def collect_signals(client, brand, *, search_news=True):
    """Enrich the brand's domain, retaining attributable company aggregates and recent brand news."""
    brand = _brand(brand)
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=90)
    cutoff_ts = int(datetime.combine(cutoff, time.min, tzinfo=timezone.utc).timestamp())
    signal, news = None, []
    domain = BRAND_DOMAINS.get(brand) or SIGNAL_DOMAINS.get(_words(brand))
    if getattr(client, "has_crustdata", True):
        domain = _domain_for(client, brand)
        data = _optional(client.company, {}, domain) if domain else {}
        signal = _company_signal(data, brand, domain, getattr(client, "observations", {}).get("/company/enrich"))
        alternate = COMPANY_FALLBACKS.get(_words(brand))
        if signal is None and alternate and domain != alternate[0]:
            lookup_domain, scope, identity_url = alternate
            data = _optional(client.company, {}, lookup_domain)
            signal = _company_signal(data, brand, lookup_domain, getattr(client, "observations", {}).get("/company/enrich"))
            if signal:
                signal.update(entity_scope=scope, identity_source_url=identity_url, brand_domain=domain)
        if signal:
            hits = [{"title": item.get("article_title"), "url": item.get("article_url"),
                     "publisher": item.get("article_publisher_name"), "date": item.get("article_publish_date"),
                     "source": "crustdata_company_news"} for item in (data.get("news") or [])
                    if isinstance(item,dict) and _published(item.get("article_publish_date"))]
            news = _relevant_news(hits, brand, cutoff, today)
        if search_news and not news:
            hits = _optional(client.search, [], f'"{brand}" India skincare product launches',
                             sources=["news"], start_date=cutoff_ts)
            news = _relevant_news(hits, brand, cutoff, today)
    if not signal and domain:
        signal = _storefront_signal(client, brand, domain, cutoff, today)
    if search_news and not news:
        news = _relevant_news(_rss_news(client, brand), brand, cutoff, today)
    return signal, news
