"""Extract observations from the primary product and its customer reviews."""
from __future__ import annotations

from datetime import datetime
import json
import re

from selectolax.lexbor import LexborHTMLParser


def _text(node):
    return " ".join(node.text(separator=" ", strip=True).split()) if node else ""


def _select(node, selectors):
    for selector in selectors.split(","):
        found = node.css_first(selector.strip())
        value = _text(found)
        if value:
            return value
    return ""


def _number(value, integer=False):
    if value is None or isinstance(value, bool):
        return None
    match = re.search(r"\d[\d,]*(?:\.\d+)?", str(value))
    if not match:
        return None
    number = float(match[0].replace(",", ""))
    return int(number) if integer else number


def _rating(value):
    n = _number(value)
    return n if n is not None and 0 <= n <= 5 else None


def _compact(fields):
    return {k: v for k, v in fields.items() if v is not None and v != "" and v != [] and v != {}}


def _records(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, list):
        for item in value:
            yield from _records(item)


def _review_date(raw):
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _review(source, ref, body, *, rating=None, title=None, date=None, verified=None, helpful=None):
    if not isinstance(body, str) or not body.strip():
        return None
    skin = re.search(r"\b(?:my|I have|I['’]ve got)\s+(?:very\s+)?(oily|combination|dry|normal|sensitive|acne[ -]prone)\s+skin\b", body, re.I)
    return dict(source=source, product_ref=ref, body=" ".join(body.split()), rating=_rating(rating),
                title=title or None, date=_review_date(date), date_text=date or None, verified=verified if type(verified) is bool else None,
                helpful_votes=_number(helpful, True), skin_type=skin[1].lower() if skin else None)


def json_product(doc):
    for n in doc.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(n.text())
        except (ValueError, TypeError):
            continue
        # Only evaluate top-level entries or @graph members, never ItemList recommendations.
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for obj in [entry, *(entry.get("@graph") or [])]:
                if isinstance(obj, dict) and "Product" in (obj.get("@type") or []):
                    return obj
    return {}


def _schema(doc, market, ref):
    product = json_product(doc)
    offer = product.get("offers") or {}
    if isinstance(offer, list):
        offer = next((o for o in offer if isinstance(o, dict) and o.get("price") is not None), {})
    if not isinstance(offer, dict):
        offer = {}
    aggregate = product.get("aggregateRating")
    aggregate = aggregate if isinstance(aggregate, dict) else {}
    price = _number(offer.get("price")) if offer.get("priceCurrency", "INR") == "INR" else None
    fields = _compact({"price": price, "rating": _rating(aggregate.get("ratingValue")),
                       "rating_count": _number(aggregate.get("ratingCount"), True),
                       "review_count": _number(aggregate.get("reviewCount"), True)})
    reviews = []
    entries = product.get("review") or []
    for row in entries if isinstance(entries, list) else [entries]:
        if not isinstance(row, dict):
            continue
        stars = row.get("reviewRating") or {}
        reviews.append(_review(market, ref, row.get("reviewBody"), title=row.get("name"),
                               rating=stars.get("ratingValue") if isinstance(stars, dict) else stars,
                               date=row.get("datePublished")))
    return fields, [r for r in reviews if r]


def _states(doc):
    decoder = json.JSONDecoder()
    for node in doc.css("script"):
        text = node.text().strip()
        if node.attributes.get("id") == "__NEXT_DATA__":
            raw = text
        else:
            match = re.match(r"(?:window\.)?__(?:PRELOADED_STATE|INITIAL_STATE)__\s*=\s*", text)
            if not match:
                continue
            raw = text[match.end():]
        try:
            yield decoder.raw_decode(raw)[0]
        except ValueError:
            continue


def _amazon(doc, ref):
    price = _select(doc, "#corePrice_feature_div .apex-pricetopay-value .a-offscreen, #corePriceDisplay_desktop_feature_div .priceToPay .a-offscreen, #corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen, #priceblock_ourprice, #priceblock_dealprice")
    mrp = _select(doc, "#corePriceDisplay_desktop_feature_div .basisPrice .a-offscreen, #corePrice_feature_div .a-text-price .a-offscreen, .priceBlockStrikePriceString")
    stars = doc.css_first("#acrPopover")
    insights = '[data-csa-c-slot-id="cr-product-insights-detail-page"]'
    summary = _select(doc, f'{insights} [data-testid="overall-summary"], [data-hook="cr-insights-ai-generated-feedback"], #product-summary p, #product-summary .a-spacing-small span')
    aspects = [_text(n) for n in doc.css('[data-hook="cr-insights-aspect-button"] [class*="a-text-bold"], [data-csa-c-slot-id="cr-insights-aspect-button"] .a-text-bold')]
    aspects.extend(_text(node) for node in doc.css(f'{insights} [data-testid="aspect-label"]'))
    ranks = []
    for n in doc.css("tr, #detailBulletsWrapper_feature_div li"):
        text = _text(n)
        if text.startswith("Best Sellers Rank"):
            ranks = [{"rank": int(rank.replace(",", "")), "category": label.strip(" \u200e|.–")}
                     for rank, label in re.findall(r"#([\d,]+)\s+in\s+([^#(]+)", text)]
            break
    fields = _compact(dict(price=_number(price), mrp=_number(mrp),
                           rating=_rating((stars.attributes.get("title") or _text(stars)) if stars else ""),
                           rating_count=_number(_select(doc, "#acrCustomerReviewText"), True),
                           bsr=ranks[0]["rank"] if ranks else None, category_ranks=ranks,
                           customers_say=summary, aspect_chips=list(dict.fromkeys(filter(None, aspects)))))
    reviews = []
    for r in doc.css('[data-hook="review"]')[:10]:
        body = _select(r, '[data-hook="reviewRichContentContainer"], [data-hook="review-body"]')
        title = _select(r, '[data-hook="reviewTitle"], [data-hook="review-title"]')
        title = re.sub(r"^\d(?:\.\d)? out of 5 stars\s*", "", title)
        date = _select(r, '[data-hook="review-date"]')
        date = re.sub(r"^Reviewed in .+? on ", "", date)
        votes = _select(r, '[data-hook="helpful-vote-statement"]')
        if votes.lower().startswith("one "):
            votes = 1
        verified = _select(r, '[data-hook="avp-badge"]')
        review = _review("amazon", ref, body, title=title, date=date, helpful=votes,
                         verified=True if "verified purchase" in verified.lower() else None,
                         rating=_select(r, '[data-hook="review-star-rating"], [data-hook="cmps-review-star-rating"]'))
        if review:
            review.update(_compact({"review_id": r.attributes.get("id"),
                                    "reviewed_variant": _select(r, '[data-hook="format-strip"]')}))
            reviews.append(review)
    return fields, [r for r in reviews if r]


def _flipkart_variant_cards(doc, ref):
    """Review pages can render separate mobile cards, each anchored by a variant label."""
    for variant in doc.css('div[dir="auto"]'):
        label = _text(variant)
        if not label.startswith("Review for:"):
            continue
        fields = list(variant.parent.iter())
        if len(fields) < 4 or fields[1].mem_id != variant.mem_id:
            continue
        header = [_text(n) for n in fields[0].css('[dir="auto"]')]
        if len(header) < 3 or header[1] != "•" or not re.fullmatch(r"[1-5](?:\.0)?", header[0]):
            continue
        footer = [_text(n) for n in fields[-1].css('[dir="auto"]')]
        stamp = next((t.lstrip("· ").strip() for t in footer if t.startswith("·")), None)
        votes = next((t.split()[-1] for t in footer if re.fullmatch(r"Helpful for [\d,]+", t)), None)
        body = _text(fields[2])
        review = _review("flipkart", ref, body, title=header[2], rating=header[0], date=stamp,
                         verified=True if "Verified Purchase" in footer else None, helpful=votes)
        if review:
            review["reviewed_variant"] = label[len("Review for:"):].strip()
            yield review


def _flipkart(doc, ref):
    fields, reviews = {}, []
    for state in _states(doc):
        multi = state.get("multiWidgetState", {}) if isinstance(state, dict) else {}
        context = multi.get("pageDataResponse", {}).get("pageContext", {})
        psi = ((context.get("fdpEventTracking") or {}).get("events") or {}).get("psi") or {}
        prices = psi.get("ppd", {})
        rating = psi.get("pr", {})
        histogram = {str(x["ratingValue"]): x["ratingCount"] for x in rating.get("individualRatingsCount", [])
                     if isinstance(x, dict) and "ratingValue" in x and "ratingCount" in x}
        fields.update(_compact(dict(price=_number(prices.get("finalPrice")), mrp=_number(prices.get("mrp")),
                                    rating_count=_number(rating.get("ratingsCount"), True),
                                    review_count=_number(rating.get("reviewsCount"), True),
                                    rating_histogram=histogram, highlights=rating.get("parameterRating"))))
        for data in _records(multi.get("widgetsData", {}).get("slots", [])):
            if data.get("type") == "ProductReviewValue":
                verified = (data.get("reviewPropertyMap") or {}).get("VERIFIED_PURCHASE", data.get("certifiedBuyer"))
                review = _review("flipkart", ref, data.get("text"), rating=data.get("rating"), title=data.get("title"),
                                 date=data.get("created"), verified=verified, helpful=data.get("helpfulCount"))
                if review:
                    attributes = {x["name"]: x["value"] for x in data.get("productAttributeList") or []
                                  if isinstance(x, dict) and x.get("name") and x.get("value")}
                    sku = re.match(r"/reviews/([A-Z0-9]+):", data.get("url") or "")
                    review.update(_compact({"reviewed_variant": attributes, "reviewed_external_id": sku[1] if sku else None}))
                    reviews.append(review)
    fields.update({k: v for k, v in _compact(dict(price=_number(_select(doc, "div.Nx9bqj.CxhGGd, div._30jeq3._16Jk6d")),
                  mrp=_number(_select(doc, r"div.yRaY8j.A6\+E6v, div._3I9_wc._2p6lqe")))).items() if k not in fields})
    if not reviews:
        for card in doc.css(".EPCmJX, ._27M-vq"):
            reviews.append(_review("flipkart", ref, _select(card, ".ZmyHeo, .t-ZTKy"),
                                   title=_select(card, ".z9E0IG, ._2-N8zT"), rating=_select(card, ".XQDdHH, ._3LWZlK")))
    if not any(reviews):
        reviews = list(_flipkart_variant_cards(doc, ref))
    return fields, [r for r in reviews if r]


def _nykaa(doc, ref):
    # Nykaa's hydrated state nests the active PDP under product/productData.
    fields = {}
    for state in _states(doc):
        for node in _records(state):
            product = next((node[k] for k in ("product", "productData", "productDetails") if isinstance(node.get(k), dict)), None)
            if not product or not any(k in product for k in ("name", "productName", "title")):
                continue
            fields = _compact(dict(price=_number(product.get("discountedPrice") or product.get("finalPrice") or product.get("salePrice") or product.get("price")),
                                   mrp=_number(product.get("mrp")), rating=_rating(product.get("rating") or product.get("averageRating")),
                                   rating_count=_number(product.get("ratingCount") or product.get("ratingsCount"), True),
                                   review_count=_number(product.get("reviewCount"), True)))
            if fields:
                return fields, []
    return fields, []


def parse_listing(market, html, product_ref):
    doc = LexborHTMLParser(html or "")
    schema, schema_reviews = _schema(doc, market, product_ref)
    fields, reviews = {"amazon": _amazon, "flipkart": _flipkart, "nykaa": _nykaa}[market](doc, product_ref)
    return {**fields, **schema}, schema_reviews + reviews


def parse_snippet(text):
    def match(pattern, integer=False):
        found = re.search(pattern, text, re.I)
        return _number(found[1], integer) if found else None
    return _compact(dict(price=match(r"(?:₹|Rs\.?\s|INR\s)\s*([\d,]+(?:\.\d+)?)"),
                         mrp=match(r"M\.?R\.?P\.?\s*:?\s*₹\s*([\d,]+(?:\.\d+)?)"),
                         rating=match(r"([0-5](?:\.\d+)?)\s*(?:out of 5|/\s*5|stars)"),
                         rating_count=match(r"([\d,]+)\s*(?:global )?ratings?\b", True),
                         review_count=match(r"([\d,]+)\s*reviews?\b", True)))
