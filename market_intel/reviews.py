"""Read public Judge.me widgets and product-specific discussions from Reddit."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit

from .catalog import clean_text
from .client import SourceUnavailable

JUDGEME_URL = "https://cdn.judge.me/reviews/reviews_for_widget"
SHOP_DOMAIN = "dot-key.myshopify.com"
SKIN = r"(?:combination|oily|sensitive|normal|dry|acne[- ]prone)"
SKIN_TYPE = re.compile(rf"\b(?:my skin (?:is|type is) |i have (?:very )?|(?:on|for) my |skin type[: ]+)"
                       rf"({SKIN}(?:\s*(?:/|and|,|to)\s*{SKIN})*)(?:\s+skin)?\b", re.I)


def _skin_type(text):
    m = SKIN_TYPE.search(text)
    return m.group(1).lower() if m else None


def _dedupe(rows):
    seen = set()
    for row in rows:
        body = " ".join(row["body"].casefold().split())
        digest = hashlib.sha256(body.encode()).hexdigest()
        if body and digest not in seen:
            seen.add(digest)
            yield row


def _widget_page(client, product, page):
    params = {"shop_domain": SHOP_DOMAIN, "platform": "shopify",
              "product_id": product["id"], "page": page, "per_page": 30}
    response = json.loads(client.get(JUDGEME_URL, params))
    if not isinstance(response, dict) or str(response.get("product_external_id")) != str(product["id"]):
        raise ValueError("Judge.me widget returned a different product or invalid payload")
    items = response.get("reviews")
    if not isinstance(items, list):
        raise ValueError("Invalid Judge.me reviews array")
    pagination = response.get("pagination") or {}
    if not isinstance(pagination, dict):
        raise ValueError("Invalid Judge.me pagination")
    return items, int(pagination.get("total_pages", page))


def collect_judgeme(client, product, pages=2):
    """Read at most `pages` widget pages, with up to 30 reviews on each page.

    Grouped widgets sometimes put reviews from sibling products first. Use a
    larger explicit page cap to recover product-specific reviews in that case.
    """
    if product.get("brand") != "Dot & Key" or not product.get("id"):
        return []
    rows = []
    for page in range(1, pages + 1):
        try:
            items, total_pages = _widget_page(client, product, page)
        except (ValueError, TypeError, SourceUnavailable) as exc:
            if not rows:
                raise SourceUnavailable(f"Judge.me page {page} unavailable: {exc}") from exc
            client.log(product["product_ref"], "partial_reviews", detail=f"Judge.me page {page}: {exc}")
            break
        for r in items:
            if not isinstance(r, dict):
                continue
            source_url = r.get("product_url") or ""
            if not isinstance(source_url, str):
                continue
            try:
                source_path = urlsplit(source_url).path.rstrip("/")
            except ValueError:
                continue
            if r.get("is_for_product_from_group") or r.get("is_for_product_from_bundle"):
                continue
            if source_path and source_path.split("/")[-1] != product["handle"]:
                continue
            raw_body = r.get("body_html") or r.get("body")
            if not isinstance(raw_body, str):
                continue
            body = clean_text(raw_body)
            if not body:
                continue
            skin_type = _skin_type(body)
            answers = r.get("cf_answers")
            for answer in answers if isinstance(answers, list) else []:
                if isinstance(answer, dict) and "skin type" in str(answer.get("question_title", "")).lower():
                    skin_type = answer.get("value") or skin_type
            rows.append({
                "source": "judgeme", "product_ref": product["product_ref"],
                "source_url": product["url"] + "#judgeme_product_reviews",
                "review_id": r.get("uuid"), "rating": r.get("rating"), "title": clean_text(r.get("title")),
                "body": body, "date": r.get("created_at"), "verified": r.get("verified_buyer"),
                "helpful_votes": r.get("thumb_up"), "skin_type": skin_type,
                "variant": r.get("product_variant_title") or None,
            })
        if not items or page >= total_pages:
            break
    return list(_dedupe(rows))


def _reddit_thread(url):
    parts = urlsplit(url or "")
    if parts.hostname not in {"reddit.com", "www.reddit.com", "old.reddit.com", "np.reddit.com"}:
        return None
    match = re.match(r"^/r/([a-z\d_]+)/comments/([a-z\d]+)(?:/|$)", parts.path, re.I)
    if match:
        return f"https://old.reddit.com/r/{match[1]}/comments/{match[2]}.json"
    return None


def _comments(listing):
    for entry in listing["data"]["children"]:
        if entry.get("kind") != "t1":
            continue
        data = entry["data"]
        yield data
        if isinstance(data.get("replies"), dict):
            yield from _comments(data["replies"])


def _words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _mentions_product(text, product):
    words = _words(text)
    brand = _words(product["brand"]) - {"and", "the"}
    if not brand <= words:
        return False
    generic = {"face", "with", "for", "the", "and", "spf", "pa", "50", "30", "new", "age", "uv",
               "filters", "in", "vivo", "tested", "skin", "all", "types", "gel", "oil", "free", "a", "e"}
    product_words = _words(product["title"]) - brand - generic
    # Require the product kind and a distinguishing term in the same context.
    kind = _words(product["category"]) | (product_words & {"balm", "toner", "cream", "serum",
                       "sunscreen", "wash", "moisturizer", "moisturiser", "mask", "conditioner", "lotion"})
    return bool(words & kind and words & (product_words - kind))


def collect_reddit(client, product, pages=2):
    """Read up to `pages` distinct Reddit threads found by the product search."""
    if pages < 1:
        return []
    hits = client.search(f'{product["brand"]} {product["title"]} review IndianSkincareAddicts',
                         site="reddit.com")
    urls = dict.fromkeys(url for hit in hits if (url := _reddit_thread(hit.get("url"))))
    rows = []
    for url in list(urls)[:pages]:
        try:
            feed = json.loads(client.get(url, {"raw_json": 1, "limit": 100}))
            post = feed[0]["data"]["children"][0]["data"]
            comments = list(_comments(feed[1]))
        except (SourceUnavailable, ValueError, IndexError, KeyError, TypeError) as exc:
            client.log(url, "reddit_thread_unavailable", detail=str(exc))
            continue
        headline = post.get("title", "")
        # Broad roundup threads often discuss multiple products. Keep a comment
        # only when its text identifies this product, or the headline is specific.
        dedicated = _mentions_product(headline, product) and not re.search(
            r"\b(?:vs\.?|versus|haul|roundup|comparison)\b|\bor\b", headline, re.I)
        for item in [post, *comments]:
            body = (item.get("body") or item.get("selftext") or "").strip()
            if not body or body in {"[removed]", "[deleted]"} or item.get("author") == "AutoModerator":
                continue
            if not dedicated and not _mentions_product(body, product):
                continue
            stamp = item.get("created_utc")
            rows.append({
                "source": "reddit", "product_ref": product["product_ref"],
                "source_url": "https://www.reddit.com" + item.get("permalink", post["permalink"]),
                "review_id": item.get("name"), "rating": None,
                "title": headline, "body": body,
                "date": datetime.fromtimestamp(stamp, timezone.utc).isoformat() if stamp else None,
                "verified": None, "helpful_votes": None, "reddit_score": item.get("score"),
                "skin_type": _skin_type(body),
            })
    return list(_dedupe(rows))
