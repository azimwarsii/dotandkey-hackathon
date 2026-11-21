"""Backfill Nykaa from server-rendered browse pages and variant records on the PDP."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import os
import re
from urllib.parse import quote, urlencode, urljoin, urlsplit

from dotenv import load_dotenv
from rapidfuzz import fuzz
from selectolax.lexbor import LexborHTMLParser

from .client import Client, SourceUnavailable
from .marketplace_parsers import _compact, _number, _rating, _review, _states
from .marketplaces import (_best_match, _is_bundle, _primary_variant, _sizes,
                           _words, canonical_listing, resolve_listing_conflicts)
from .store import Store

SITE = "https://www.nykaa.com/"
BRAND_PAGE = SITE + "brands/dot-key/c/7675"
# Manually cross-checked ingredient, format, shade and size declarations for
# renamed products. The Nykaa child ID and original catalog SKU must still match.
VERIFIED_VARIANTS = {
    "dk:6887708786853": ("DK_NVDPMFC", "8198104", "Deep Pore Clean Milky Foam Cleanser on both product URLs, 100 ml."),
    "dk:7417266372773": ("DK_MPAM", "4432226", "Pea Peptide Strengthening Moringa & Argan Hair Mask on both product URLs, 200 ml."),
    "dk:5898353737893": ("DK_MNLSMH", "4873206", "Vitamin C + E Lip Plumping Sleeping Mask, Lingonberry shade, 15 ml."),
    "dk:4691400360068": ("DK_AGCM", "552262", "PDP explicitly lists French green clay and Centella in the 85 g salicylic green clay mask."),
    "dk:8137230778533": ("DK_PMRM", "8978857", "Both URLs identify Pomegranate Miracle Vitamin E Revitalizing Moisturizer SPF 30, 60 ml."),
    "dk:4849621237892": ("DK_NRST", "751415", "Retinol and Ceramide anti-ageing night repair cream, 60 ml child of the two-size PDP."),
    "competitor:sunscreen:amazon:B082PFY9S7": (None, "76006", "Neutrogena Ultra Sheer SPF 50+ PA++++, 80 g and untinted, both product pages."),
    "competitor:body:amazon:B0H65F539G": (None, "28675771", "Mamaearth Vitamin C Daily Glow Body Lotion with Vitamin C and Honey, 600 ml."),
    "competitor:face-wash:amazon:B096PJMGPL": (None, "1467106", "Minimalist 2% Salicylic Acid + LHA acne cleanser, 100 ml."),
    "competitor:hair:amazon:B01NBYEC2W": (None, "825658", "TRESemme Keratin Smooth anti-frizz treatment hair mask, 300 ml."),
    "competitor:mask:amazon:B0D2RQMS7Q": (None, "15533653", "Foxtale De-Tan brightening face mask, 75 g."),
    "competitor:mask:amazon:B00OCJ5SW0": (None, "23998", "Plum Green Tea Clear Face Mask, 60 g."),
    "competitor:mask:amazon:B08VGBD2NM": (None, "1172655", "The Derma Co 2% Salicylic Acid face mask for acne and blemish-prone skin, 50 g."),
    "competitor:moisturiser:amazon:B0GHXYQ318": (None, "25019389", "Cetaphil Moisturising Lotion, 59 ml."),
    "competitor:moisturiser:amazon:B09Q3MWP2S": (None, "4524075", "Minimalist Vitamin B5 10% oil-free moisturizer, 50 g."),
    "competitor:serum:flipkart:KMTH89D4ZVZMESB7": (None, "19850277", "Chemist at Play 10% Vitamin C brightening face serum, 10 ml."),
    "competitor:serum:amazon:B01MDTVZTZ": (None, "5003164", "The Ordinary Niacinamide 10% + Zinc 1% face serum, 30 ml."),
    "competitor:toner:flipkart:TNRHFYKPYNMESZSD": (None, "16275884", "Chemist at Play Gentle Exfoliating Toner with glycolic and mandelic acids and kombucha, 150 ml."),
    "competitor:toner:flipkart:TNRHFPSXFHF5DXAT": (None, "15708996", "Foxtale Glow Toner + Makeup Setting Spray with vitamin C and niacinamide, 150 ml."),
    "competitor:toner:flipkart:TNRGFUZHNW3YRJKR": (None, "1130913", "Minimalist 3% polyhydroxy acid PHA toner, 150 ml."),
    "competitor:toner:flipkart:TNRGAES4PZRFZYHG": (None, "4516637", "Plum 3% Niacinamide & Rice Water toner, 150 ml."),
    "competitor:toner:flipkart:TNRGXYYYKQGYZPVX": (None, "14157069", "Plix Jamun Clarifying Fruity Toner, 150 ml."),
    "competitor:eye:flipkart:ECMGUNKEFBP9SX4G": (None, "12810512", "Minimalist Vitamin K + Retinal 01% Under Eye Cream, 14 g."),
    "competitor:eye:amazon:B08TTW5RJG": (None, "1172652", "The Derma Co 5% Caffeine Under Eye Serum with retinol and peptide, 15 ml."),
    "competitor:eye:flipkart:ECMGHQR8YUZHNGHX": (None, "7292096", "mCaffeine Coffee Under Eye Cream for Dark Circles and Puffiness, 15 ml."),
}
PACK = re.compile(r"\b(?:combo|freebie|kit)\b", re.I)


class NykaaClient(Client):
    def _pace(self, bucket, limit, window):
        if bucket.endswith("/web/enrich/live"):
            limit = min(limit, 9)
        return super()._pace(bucket, limit, window)


def _page_state(html):
    return next((s for s in _states(LexborHTMLParser(html or ""))
                 if isinstance(s, dict) and any(k in s for k in ("productPage", "categoryListing", "searchListingPage"))), {})


def browse_cards(html, search=False):
    state = _page_state(html)
    listing = state.get("searchListingPage" if search else "categoryListing") or {}
    data = listing.get("listingData") or {}
    return [r for r in data.get("products", []) if r.get("slug") and r.get("name")], data.get("totalFound", 0)


def variant_rows(html, source_url, captured_at):
    """Extract all advertised sibling offers; keep aggregate and review scopes explicit."""
    state = _page_state(html)
    p = (state.get("productPage") or {}).get("product") or {}
    parent = str(p.get("parentId") or p.get("id") or "")
    canonical = canonical_listing("nykaa", source_url)
    if not parent.isdigit() or not canonical or p.get("isKitCombo") or _is_bundle(p.get("name", "")):
        return []
    source_pid = re.search(r"/p/(\d+)", urlsplit(source_url).path)[1]
    known_ids = {parent, str(p.get("id")), str(p.get("selectedVariantId")),
                 *(str(v.get("childId")) for v in p.get("variants", []))}
    if source_pid not in known_ids:
        return []
    configured = p.get("productType") == "configurable" or bool(p.get("variants")) or str(p.get("id")) != parent
    variants = p.get("variants") or [p]
    rows = []
    for v in variants:
        child = str(v.get("childId") or v.get("selectedVariantId") or v.get("id") or "")
        if not child.isdigit():
            continue
        slug = v.get("slug") or p.get("slug") or urlsplit(source_url).path
        url = urljoin(SITE, slug)
        if configured:
            url += "?" + urlencode({"skuId": child})
        identity = canonical_listing("nykaa", url)
        if not identity or identity[0] != child:
            continue
        name = v.get("name") or p.get("name")
        variant_name = str(v.get("variantName") or v.get("selectedVariantName") or "")
        pack = str(v.get("packSize") or "")
        text = " ".join(filter(None, [name, variant_name]))
        if _is_bundle(text) or PACK.search(text):
            continue
        snapshot = _compact({
            "price": _number(v.get("offerPrice")), "mrp": _number(v.get("mrp")),
            "rating": _rating(p.get("rating")), "rating_count": _number(p.get("ratingCount"), True),
            "review_count": _number(p.get("reviewCount"), True), "captured_at": captured_at,
            "source": "nykaa_pdp_state", "url": source_url, "currency": "INR",
            "rating_scope": "parent_product" if configured else "selected_variant",
            "rating_scope_id": parent if configured else child,
            "price_scope": "selected_variant", "nykaa_variant_id": child,
            "nykaa_parent_id": parent, "nykaa_merchant_sku": v.get("sku"),
        })
        if snapshot.get("rating") == 0:
            snapshot.pop("rating")
        reviews = []
        for item in p.get("latestReviews") or []:
            rid = str(item.get("variantId") or "")
            if rid != child and not (not configured and not rid):
                continue
            r = _review("nykaa", None, item.get("description"), rating=item.get("rating"),
                        title=item.get("title"), date=item.get("createdOn"),
                        verified=item.get("isBuyer"), helpful=item.get("likeCount"))
            if r:
                reviews.append(dict(r, url=identity[1], review_id=str(item.get("id") or "") or None,
                                    reviewed_external_id=child, observed_at=captured_at))
        rows.append({"market": "nykaa", "url": identity[1], "external_id": child, "title": text,
                     "brand": v.get("brandName") or p.get("brandName"), "size": pack,
                     "source_url": source_url, "captured_at": captured_at,
                     "snapshot": snapshot, "reviews": reviews})
    return rows


def _peer_cards(product, cards):
    brand = "".join(_words(product["brand"]))
    candidates = []
    for row in cards:
        row_brand = "".join(_words(row.get("brandName")))
        if not row_brand or not (row_brand in brand or brand in row_brand) or _is_bundle(row["name"]):
            continue
        relevance = fuzz.token_set_ratio(" ".join(_words(product["title"])), " ".join(_words(row["name"])))
        if relevance >= 54:
            candidates.append((relevance, row))
    candidates.sort(key=lambda item: -item[0])
    return [r for _, r in candidates[:4]]


def _fetch(client, urls, cached_only):
    urls = list(dict.fromkeys(urls))
    for i in range(0, len(urls), 8):
        batch = urls[i:i+8]
        if cached_only:
            result = {url: client._read(["html", url, False], url) or client._read(["html", url, True], url)
                      for url in batch}
        else:
            if not client.has_crustdata:
                raise SourceUnavailable("Nykaa backfill requires Crustdata web enrichment")
            result = client.enrich(batch)
            missing = [url for url in batch if not result.get(url)]
            if missing:
                result.update(client.enrich(missing, human_mode=True))
        for url, html in result.items():
            if html:
                yield url, html, client.observations[url]


def _search_url(p):
    name = p["title"].split("|")[0]
    return SITE + "search/result/?q=" + quote(" ".join(name.split()[:11]))


def _brand_key(value):
    words = " ".join(_words(value))
    return {"the plant fix plix": "plix", "plix the plant fix": "plix"}.get(words, words)


def _same_pa_grade(a, b):
    def grades(title):
        return set(re.findall(r"\bpa\s*(\+{1,4})", str(title or ""), re.I))
    first, second = grades(a), grades(b)
    return not first or not second or bool(first & second)


def _match_all(client, products, rows):
    matches = []
    origins = {}
    for p in products:
        # Require the observed pack size in the PDP itself. The shipping weight of
        # the parcel and the storefront's default size do not identify a child SKU.
        size = _sizes(p.get("size"))
        if not size:
            continue
        choices = [r for r in rows if _sizes(r["size"]) == size or (not _sizes(r["size"]) and _sizes(r["title"]) == size)]
        choices = [r for r in choices if _same_pa_grade(p["title"], r["title"])]
        listing = None
        verified = VERIFIED_VARIANTS.get(p["product_ref"])
        if verified and verified[0] == _primary_variant(p).get("sku"):
            candidate = next((r for r in choices if r["external_id"] == verified[1] and
                              _brand_key(r["brand"]) == _brand_key(p["brand"])), None)
            if candidate:
                listing = {k:candidate.get(k) for k in ("market","url","external_id","title","size","brand","source_url")}
                listing.update(product_ref=p["product_ref"], confidence=1.0, match_method="manual",
                               verification_url=p.get("url"), verification_note=verified[2])
        if listing is None:
            listing = _best_match(client, p, "nykaa", choices, "nykaa_pdp_variant")
        if not listing:
            continue
        row = next(r for r in choices if r["url"] == listing["url"] and r["title"] == listing["title"])
        listing.update(discovered_at=row["captured_at"], matched_variant_sku=_primary_variant(p).get("sku"))
        matches.append(listing)
        origins[p["product_ref"], row["external_id"]] = row
    return [(match, origins[match["product_ref"], match["external_id"]])
            for match in resolve_listing_conflicts(matches)]


def backfill(client, store, *, cached_only=False):
    categories = [row[0] for row in store.db.execute(
        "SELECT DISTINCT category FROM product WHERE is_competitor=0 AND is_combo=0 ORDER BY category != 'Sunscreen',category")]
    products = [p for category in categories for p in store.report(category)["products"] if not p.get("is_combo")]
    peers = [p for p in products if not p["product_ref"].startswith("dk:") and p.get("size")]
    cards = []
    base = next(_fetch(client, [BRAND_PAGE], cached_only), None)
    if base:
        first, total = browse_cards(base[1])
        cards.extend(first)
        if first:
            pages = range(2, math.ceil(int(total)/len(first))+1)
            for _, html, _ in _fetch(client, (BRAND_PAGE + "?page_no=" + str(p) for p in pages), cached_only):
                cards.extend(browse_cards(html)[0])
    searches = {_search_url(p):p for p in peers}
    for url, html, _ in _fetch(client, searches, cached_only):
        cards.extend(_peer_cards(searches[url], browse_cards(html, search=True)[0]))
    urls = [urljoin(SITE,c["slug"]) for c in cards if not PACK.search(c["name"]) and not _is_bundle(c["name"])]
    rows = []
    for url, html, stamp in _fetch(client, sorted(set(urls), key=lambda s: ("sunscreen" not in s,s)), cached_only):
        rows.extend(variant_rows(html,url,stamp))
    saved = []
    for listing, source in _match_all(client, products, rows):
        ref = listing["product_ref"]
        # Preserve an earlier verified listing; only enrich the same identity.
        conflicts = store.db.execute("SELECT product_ref,external_id FROM listing WHERE market='nykaa' "
                                     "AND (product_ref=? OR external_id=?)", (ref,listing["external_id"])).fetchall()
        if any(tuple(r) != (ref,listing["external_id"]) for r in conflicts):
            continue
        store.save_listing(listing, source["snapshot"], [dict(r,product_ref=ref) for r in source["reviews"]])
        saved.append({"product_ref":ref,"external_id":listing["external_id"],"confidence":listing["confidence"]})
    return {"matched":len(saved),"target_products":len(products),"candidate_variants":len(rows),"listings":saved}


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("MARKET_INTEL_DB","data/market-intel.sqlite3"))
    parser.add_argument("--cache", default="data/cache")
    parser.add_argument("--cached-only", action="store_true")
    args = parser.parse_args()
    with closing(Store(args.db)) as target, closing(NykaaClient(args.cache,target.log)) as transport:
        print(json.dumps(backfill(transport,target,cached_only=args.cached_only),indent=2))
