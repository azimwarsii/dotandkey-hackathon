"""Daily, atomic Shopify catalog snapshots and observation-backed launch/price events."""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote, urlencode

from rapidfuzz import fuzz

from .catalog import clean_text, size_in
from .client import Client, SourceUnavailable
from .competitors import BRAND_DOMAINS, _published
from .trends import normalize

BRANDS = tuple("Minimalist|Foxtale|The Derma Co|Deconstruct|Plum|Re'equil|Pilgrim|Aqualogica|Mamaearth".split("|"))
IST = timezone(timedelta(hours=5, minutes=30))
EXCLUDE = re.compile(r"\b(?:combo|combos|bundle|bundles|duo|trio|kit|kits|hamper|gift|gwp|"
                     r"sample|sampler|trial pack|freebie|freebies|multiple pack|multipack|set of|pack of (?:[2-9]|\d{2,})|"
                     r"buy (?:one|[1-9]) get|pick any|build your own|routine set)\b", re.I)
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS snapshot(
 brand TEXT NOT NULL, day TEXT NOT NULL, source_url TEXT NOT NULL, observed_at TEXT NOT NULL,
 item_count INTEGER NOT NULL, PRIMARY KEY(brand,day));
CREATE TABLE IF NOT EXISTS currency_observation(
 brand TEXT NOT NULL, day TEXT NOT NULL, code TEXT, source_url TEXT NOT NULL,
 PRIMARY KEY(brand,day), FOREIGN KEY(brand,day) REFERENCES snapshot(brand,day));
CREATE TABLE IF NOT EXISTS observation(
 brand TEXT NOT NULL, day TEXT NOT NULL, id TEXT NOT NULL, category TEXT, excluded INTEGER NOT NULL,
 data TEXT NOT NULL, PRIMARY KEY(brand,day,id), FOREIGN KEY(brand,day) REFERENCES snapshot(brand,day));
CREATE INDEX IF NOT EXISTS observation_identity ON observation(brand,id,day);
CREATE INDEX IF NOT EXISTS observation_category ON observation(category,day);
"""


def _money(value):
    try:
        result = float(value)
        return result if result >= 0 else None
    except (TypeError, ValueError):
        return None


def _exclude(title, kind, tags):
    label = normalize(title)
    if EXCLUDE.search(label) or EXCLUDE.search(normalize(kind)):
        return True
    if normalize(kind) in {"free", "set", "sets", "gift cards", "merchandise", "accessories", "free product"}:
        return True
    if re.search(r"^(?:free\b|complimentary\b)|\b(?:for free|free (?:gift|sample|scrunchie|pouch|bag))\b", label):
        return True
    if re.search(r"\b(?:pouch|vanity bag|gift card|spatula|face roller|headband|tote bag|empty bottle)\b", label):
        return True
    if re.search(r"\b(?:\d+\s*(?:g|gm|ml)|shampoo|conditioner|mask|serum|cream|wash|toner)\s*[+&]\s*"
                 r".{0,60}\b(?:\d+\s*(?:g|gm|ml)|shampoo|conditioner|mask|serum|cream|wash|toner)\b", title, re.I):
        return True
    return any(normalize(tag) in {"combo", "bundle", "gwp", "free gift", "gift with purchase", "gift card"} for tag in tags)


def _normalize_product(raw, brand, domain, currency):
    from .attributes import category_for
    identifier = str(raw["id"])
    title = raw["title"].strip()
    kind = raw.get("product_type") or ""
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
    variants = [{"id": str(v["id"]), "title": v.get("title"), "sku": v.get("sku"),
                 "price": _money(v.get("price")), "mrp": _money(v.get("compare_at_price")),
                 "size": size_in(v.get("title")), "available": v.get("available")}
                for v in raw.get("variants", []) if v.get("id") is not None]
    selected = next((v for v in variants if v["available"]), variants[0] if variants else {})
    p = {"product_ref": f"shopify:{domain}:{identifier}", "shopify_id": identifier, "brand": brand,
         "title": title, "handle": raw["handle"], "product_type": kind,
         "url": f"https://{domain}/products/{quote(raw['handle'])}", "tags": tags,
         "description": clean_text(raw.get("body_html")), "variants": variants,
         "price": selected.get("price"), "mrp": selected.get("mrp"), "currency": currency,
         "size": selected.get("size") or size_in(title), "created_at": raw.get("created_at"),
         "published_at": raw.get("published_at"), "is_combo": _exclude(title, kind, tags)}
    p["category"] = category_for(p)
    return p


def _get_today(client, url, day, params=None):
    value = client.get(url, params=params) if params else client.get(url)
    requested = url + "?" + urlencode(params) if params else url
    observed = getattr(client, "observations", {}).get(requested)
    if observed and datetime.fromisoformat(observed).astimezone(IST).date() != day:
        # Yesterday's response may still be within the shared HTTP cache TTL.
        previous = client.refresh
        try:
            client.refresh = True
            value = client.get(url, params=params) if params else client.get(url)
        finally:
            client.refresh = previous
        observed = client.observations.get(requested)
        if not observed or datetime.fromisoformat(observed).astimezone(IST).date() != day:
            raise SourceUnavailable(f"{requested} did not produce a current-day observation")
    return value


def _fetch(client, brand, day, currency):
    domain = BRAND_DOMAINS[brand]
    root = f"https://{domain}/products.json"
    rows, page = {}, 1
    while True:
        params = {"limit": 250, "page": page}
        raw = json.loads(_get_today(client, root, day, params=params))
        products = raw.get("products") if isinstance(raw, dict) else None
        if not isinstance(products, list):
            raise SourceUnavailable(f"{domain} returned no products array")
        if not products:
            if not rows:
                raise SourceUnavailable(f"{domain} returned an empty catalog on the first page")
            break
        before = len(rows)
        for p in products:
            record = _normalize_product(p, brand, domain, currency)
            rows[record["shopify_id"]] = record
        if len(rows) == before:
            raise SourceUnavailable(f"{domain} repeated a product page")
        page += 1
    first_url = root + "?" + urlencode({"limit": 250, "page": 1})
    stamp = getattr(client, "observations", {}).get(first_url)
    if stamp and datetime.fromisoformat(stamp).astimezone(IST).date() != day:
        raise SourceUnavailable(f"{brand} first response predates the requested observation day")
    return root, stamp or datetime.now(timezone.utc).isoformat(), rows.values()


def _currency(client, brand, day):
    url = f"https://{BRAND_DOMAINS[brand]}/cart.js"
    try:
        code = json.loads(_get_today(client, url, day)).get("currency")
        return (code if isinstance(code, str) and re.fullmatch(r"[A-Z]{3}", code) else None), url
    except (SourceUnavailable, ValueError, TypeError, AttributeError, OSError):
        return None, url


def snapshot_catalogs(client, path, as_of):
    """Commit a brand only after its complete feed has been fetched. Reruns resume failures."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {"date": str(as_of), "brands": {}, "errors": {}}
    with closing(sqlite3.connect(path, timeout=30)) as db:
        db.executescript(SCHEMA)
        for brand in BRANDS:
            old = db.execute("SELECT item_count FROM snapshot WHERE brand=? AND day=?", (brand, str(as_of))).fetchone()
            if old:
                if not db.execute("SELECT 1 FROM currency_observation WHERE brand=? AND day=?",
                                  (brand, str(as_of))).fetchone():
                    currency, source_url = _currency(client, brand, as_of)
                    with db:
                        db.execute("INSERT OR IGNORE INTO currency_observation VALUES(?,?,?,?)",
                                   (brand, str(as_of), currency, source_url))
                summary["brands"][brand] = old[0]
                continue
            try:
                currency, source_url = _currency(client, brand, as_of)
                root, stamp, rows = _fetch(client, brand, as_of, currency)
                with db:
                    saved = db.execute("INSERT OR IGNORE INTO snapshot VALUES(?,?,?,?,?)",
                                       (brand, str(as_of), root, stamp, len(rows)))
                    if saved.rowcount:
                        db.execute("INSERT INTO currency_observation VALUES(?,?,?,?)", (brand, str(as_of), currency, source_url))
                        db.executemany("INSERT INTO observation VALUES(?,?,?,?,?,?)",
                                       ((brand, str(as_of), p["shopify_id"], p["category"], int(p["is_combo"]),
                                         json.dumps(p, ensure_ascii=False, separators=(",", ":"))) for p in rows))
                summary["brands"][brand] = len(rows)
            except (SourceUnavailable, OSError, TypeError, KeyError, ValueError) as exc:
                summary["errors"][brand] = str(exc)
    return summary


def _readonly(path):
    resolved = Path(path).resolve()
    return sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True)


def latest_snapshot_date(path):
    if not Path(path).is_file():
        return None
    with closing(_readonly(path)) as db:
        row = db.execute("SELECT MAX(day) FROM snapshot").fetchone()
    return _published(row[0]) if row else None


def _discount(price, mrp):
    return 1 - price / mrp if price is not None and mrp and 0 <= price <= mrp else None


def _changes(product, latest, previous):
    """Compare the same variant in two actual snapshots, never two pack sizes."""
    if not product.get("currency") or previous.get("currency") != product["currency"]:
        return []
    old = {v["id"]: v for v in previous["variants"]}
    days = (date.fromisoformat(latest) - date.fromisoformat(previous["observed_date"])).days
    changes = []
    for v in product["variants"]:
        prior = old.get(v["id"])
        if not prior or (v["price"], v["mrp"]) == (prior["price"], prior["mrp"]):
            continue
        before, after = _discount(prior["price"], prior["mrp"]), _discount(v["price"], v["mrp"])
        delta = after - before if before is not None and after is not None else None
        changes.append({"brand": product["brand"], "title": product["title"], "url": product["url"],
                        "product_ref": product["product_ref"], "currency": product["currency"], "variant_id": v["id"], "days": days,
                        "from_date": previous["observed_date"], "to_date": latest, "price_before": prior["price"],
                        "price_after": v["price"], "discount_before": before, "discount_after": after,
                        "discount_change": delta, "discount_change_30d": delta if days == 30 else None})
    return changes


def _group_products(products):
    groups = defaultdict(list)
    for p in products:
        # Identical titles with different advertised variants remain distinct.
        variants = tuple(sorted(normalize(v.get("title")) for v in p.get("variants", [])))
        key = (p["brand"], normalize(p["title"]), normalize(p.get("size")), variants)
        groups[key].append(p)
    result = []
    for copies in groups.values():
        copies.sort(key=lambda p: (p["first_seen"], p.get("created_at") or "9999", p["product_ref"]))
        result.append(dict(copies[0], related_product_refs=[p["product_ref"] for p in copies[1:]]))
    return result


def catalog_context(path, category, as_of):
    from .attributes import CATEGORY_NAMES
    category = CATEGORY_NAMES.get(str(category).casefold(), category)
    result = {"as_of": str(as_of), "products": [], "historical_products": [], "launches": [], "price_changes": [],
              "coverage": [], "asin_changes": [], "amazon_snapshot_count": 0}
    if not Path(path).is_file():
        result["coverage"] = [{"brand": b, "status": "no_snapshot"} for b in BRANDS]
        return result
    cutoff = as_of - timedelta(days=89)
    with closing(_readonly(path)) as db:
        result["asin_changes"], result["amazon_snapshot_count"] = _asin_changes(db, category, as_of)
        for brand in BRANDS:
            snapshots = db.execute("SELECT day, item_count, source_url FROM snapshot WHERE brand=? AND day<=? ORDER BY day",
                                   (brand, str(as_of))).fetchall()
            coverage = {"brand": brand, "status": "available" if snapshots else "no_snapshot",
                        "snapshot_count": len(snapshots)}
            result["coverage"].append(coverage)
            if not snapshots:
                continue
            baseline, latest = snapshots[0][0], snapshots[-1][0]
            coverage.update(first_snapshot=baseline, last_snapshot=latest, item_count=snapshots[-1][1],
                            source_url=snapshots[-1][2], observed_on_as_of=(latest == str(as_of)))
            currencies = dict(db.execute("SELECT day,code FROM currency_observation WHERE brand=? AND day<=?",
                                         (brand, str(as_of))))
            coverage["currency"] = currencies.get(latest)
            coverage["currency_source"] = f"https://{BRAND_DOMAINS[brand]}/cart.js"
            rows = db.execute("""SELECT day,data FROM observation WHERE brand=? AND day<=? AND id IN (
                SELECT id FROM observation WHERE brand=? AND category=? COLLATE NOCASE AND day<=?)
                ORDER BY id,day""", (brand, str(as_of), brand, category, str(as_of)))
            histories = defaultdict(list)
            for day, data in rows:
                p = json.loads(data)
                p.update(currency=currencies.get(day), observed_date=day)
                histories[p["shopify_id"]].append(p)
            for history in histories.values():
                initial, p = history[0], history[-1]
                first_seen = date.fromisoformat(initial["observed_date"])
                p["first_seen"] = initial["first_seen"] = str(first_seen)
                if p["observed_date"] == latest and p["category"] == category and not p["is_combo"]:
                    result["products"].append(p)
                    for earlier in history[:-1]:
                        gap = (date.fromisoformat(latest) - date.fromisoformat(earlier["observed_date"])).days
                        if earlier is history[-2] or gap == 30:
                            result["price_changes"].extend(_changes(p, latest, earlier))
                # A reclassified product only contributes its launch once, in the
                # category and with the terms seen when that ID first appeared.
                if initial["category"] != category or initial["is_combo"]:
                    continue
                result["historical_products"].append(initial)
                created = _published(initial.get("created_at"))
                baseline_observation = first_seen.isoformat() == baseline
                event_date = created if baseline_observation else first_seen
                if event_date is None or not cutoff <= event_date <= as_of:
                    continue
                result["launches"].append({**{k: initial[k] for k in ("product_ref", "brand", "title", "category", "url",
                                                                      "created_at", "published_at", "first_seen")},
                                           "date": str(event_date),
                                           "launch_basis": "recent_created_at_on_baseline" if baseline_observation else "first_seen_after_baseline",
                                           "evidence_urls": [initial["url"], snapshots[-1][2]]})
    # Some stores generate affiliate and campaign copies of identical products.
    # Keep every ID in history, but count exact brand/title/pack matches once.
    current = _group_products(result["products"])
    history = _group_products(result["historical_products"])
    canonical = {p["product_ref"]: p for p in history}
    result["products"], result["historical_products"] = current, history
    result["launches"] = [dict(event, related_product_refs=canonical[event["product_ref"]]["related_product_refs"])
                          for event in result["launches"] if event["product_ref"] in canonical]
    result["launches"].sort(key=lambda e: (e["date"], e["product_ref"]), reverse=True)
    return result


def snapshot_asins(client, path, as_of):
    """Capture one public Amazon result page per category for later appearance checks."""
    from .attributes import CATEGORY_RULES
    from .competitors import _category, _page_url, parse_category_page
    result = {}
    with closing(sqlite3.connect(path, timeout=30)) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS amazon_search(
                      day TEXT NOT NULL, category TEXT NOT NULL, source_url TEXT NOT NULL,
                      results TEXT NOT NULL, PRIMARY KEY(day,category))""")
        for category, _ in CATEGORY_RULES:
            existing = db.execute("SELECT results FROM amazon_search WHERE day=? AND category=?",
                                  (str(as_of), category)).fetchone()
            if existing:
                result[category] = len(json.loads(existing[0]))
                continue
            rows = []
            error = "No current-day product cards on the first two result pages"
            for page in (1, 2):
                url = _page_url("amazon", _category(category)[0], page, False)
                try:
                    rows = parse_category_page(_get_today(client, url, as_of), "amazon", url)
                except (SourceUnavailable, OSError, ValueError) as exc:
                    error = str(exc)
                if rows:
                    break
            if not rows:
                result[category] = {"unavailable": error}
                continue
            cards = [{k: r.get(k) for k in ("external_id", "title", "brand", "url", "position")} for r in rows]
            with db:
                db.execute("INSERT OR IGNORE INTO amazon_search VALUES(?,?,?,?)",
                           (str(as_of), category, url, json.dumps(cards, ensure_ascii=False)))
            result[category] = len(cards)
    return result


def _asin_changes(db, category, as_of):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='amazon_search'").fetchone():
        return [], 0
    rows = db.execute("SELECT day,source_url,results FROM amazon_search WHERE category=? COLLATE NOCASE AND day<=? ORDER BY day",
                      (category, str(as_of))).fetchall()
    changes, previous_by_url = [], {}
    for observed, url, raw in rows:
        cards = json.loads(raw)
        prior = previous_by_url.get(url)
        if prior is not None and date.fromisoformat(observed) >= as_of - timedelta(days=89):
            changes.extend({**card, "date": observed, "previous_date": prior[0],
                            "source_url": url, "type": "new_to_sampled_amazon_page"}
                           for card in cards if card["external_id"] not in prior[1])
        previous_by_url[url] = observed, {c["external_id"] for c in cards}
    return changes, len(rows)


GENERIC = set("the a with and of for on face body hair skin skincare product products launches new introducing "
              "introduces unveils in india men women pack bottle cream wash mask serum sunscreen toner shampoo "
              "conditioner moisturizer moisturiser lip balm under eye stick spf pa g gm ml kg gel lotion tinted "
              "size de la co all free daily natural set store sale buy shop online best".split())


def _same_product(launch, row):
    brand = normalize(launch["brand"])
    candidate = normalize(str(row.get("title") or "") + " " + str(row.get("snippet") or ""))
    if normalize(row.get("brand")) != brand and f" {brand} " not in f" {candidate} ":
        return False
    left = set(normalize(launch["title"]).split()) - set(brand.split()) - GENERIC
    right = set(candidate.split()) - set(brand.split()) - GENERIC
    distinctive = {x for x in left if len(x) >= 3 and not x.isdigit()}
    if len(distinctive & right) < 2 or len(distinctive & right) < len(distinctive) * 0.65:
        return False
    for pattern in [r"\bspf\s*(\d+)", r"(\d+(?:\.\d+)?)\s*%"]:
        l = set(re.findall(pattern, launch["title"].lower()))
        r = set(re.findall(pattern, (row.get("title") or "").lower()))
        if l and r and l != r:
            return False
    return fuzz.token_set_ratio(" ".join(sorted(left)), " ".join(sorted(right))) >= 76


def corroborate_launches(raw_report, context):
    by_product = defaultdict(list)
    for review in raw_report.get("reviews", []):
        when = _published(review.get("date"))
        if when and (not context.get("as_of") or str(when) <= context["as_of"]):
            by_product[review.get("product_ref")].append((when, review))
    products = raw_report.get("products", [])
    result = []
    for launch in context.get("launches", []):
        checks = []
        for p in products:
            if not _same_product(launch, p):
                continue
            reviews = by_product.get(p.get("product_ref")) or []
            if reviews:
                earliest, evidence = min(reviews, key=lambda entry: entry[0])
                checks.append({"type": "earliest_observed_review", "date": str(earliest),
                               "predates_launch_signal": str(earliest) < launch["date"],
                               "product_ref": p["product_ref"], "source": evidence.get("source"),
                               "url": evidence.get("source_url") or evidence.get("url") or p.get("url")})
        for news in raw_report.get("news_items", []):
            if news.get("event_type") == "marketplace_new_arrival" or not news.get("url"):
                continue
            when = _published(news.get("date"))
            if not when or (context.get("as_of") and str(when) > context["as_of"]):
                continue
            text = (news.get("title") or "") + " " + (news.get("snippet") or "")
            if re.search(r"\b(?:launch(?:es|ed|ing)?|introduc(?:es|ed)|unveils?|new)\b", text, re.I) and _same_product(launch, news):
                checks.append({"type": "matching_launch_news", "title": news.get("title"), "source": news.get("source"),
                               "date": str(when), "url": news["url"]})
        for asin in context.get("asin_changes", []):
            if _same_product(launch, asin):
                checks.append(asin)
        result.append({**launch, "crosschecks": checks})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/competitor-catalogs.sqlite3")
    parser.add_argument("--cache", default="data/cache")
    args = parser.parse_args()
    with closing(Client(args.cache, lambda *a, **kw: None)) as client:
        day = datetime.now(IST).date()
        result = snapshot_catalogs(client, args.db, day)
        result["amazon_pages"] = snapshot_asins(client, args.db, day)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
