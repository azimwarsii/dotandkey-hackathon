"""Descriptive metrics for one category as of a UTC date. All evidence is observed."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median

from .aspects import LEXICON_PATH, lexicon, merge_polarities, sentences, tag_sentence

VALIDATION_PATH = Path(__file__).resolve().parents[1] / "validation" / "aspect_precision.json"
PRIOR_WEIGHT = 50
Z95 = 1.959963984540054


def utc_date(value):
    if isinstance(value, datetime):
        return (value.astimezone(timezone.utc) if value.tzinfo else value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return utc_date(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _number(v):
    if isinstance(v, bool):
        return None
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _rating(value):
    value = _number(value)
    return value if value is not None and 1 <= value <= 5 else None


def _average(total, n):
    return total / n if n else None


def _median(numbers):
    return median(numbers) if numbers else None


def _wilson(pos, n):
    if n < 30:
        return None
    p = pos / n
    z2 = Z95**2
    center = p + z2/(2*n)
    radius = Z95 * math.sqrt((p*(1-p) + z2/(4*n))/n)
    return [max(0, (center-radius)/(1+z2/n)), min(1, (center+radius)/(1+z2/n))]


@lru_cache(maxsize=1)
def _validation():
    report = json.loads(VALIDATION_PATH.read_text())
    valid = (report["lexicon_sha256"] == hashlib.sha256(LEXICON_PATH.read_bytes()).hexdigest()
             and report["tagger_sha256"] == hashlib.sha256(Path(__file__).with_name("aspects.py").read_bytes()).hexdigest())
    return {**report, "version_matches": valid}


def review_evidence(row, quote=None):
    body = row.get("body") or ""
    ref = row.get("product_ref")
    review_id = row.get("review_id") or hashlib.sha256((str(ref)+"\n"+body).encode()).hexdigest()[:20]
    return {"product_ref": ref, "review_id": review_id, "quote": (quote or body).strip()[:260],
            "source": row.get("source"), "url": row.get("source_url") or row.get("url"),
            "rating": _rating(row.get("rating")), "date": row.get("date")}


def _examples(items, limit=3):
    result, ids = [], set()
    for e in items:
        if e["review_id"] not in ids:
            ids.add(e["review_id"])
            result.append(e)
            if len(result) == limit:
                break
    return result


def _review_sample(report, refs, as_of):
    sample = []
    seen = set()
    excluded = Counter()
    for raw in report.get("reviews", []):
        if raw.get("product_ref") not in refs:
            continue
        body = (raw.get("body") or "").strip()
        day = utc_date(raw.get("date"))
        observed = utc_date(raw.get("observed_at"))
        if not body:
            excluded["empty_body"] += 1
            continue
        if (day and day > as_of) or (observed and observed > as_of):
            excluded["after_cutoff"] += 1
            continue
        if day is None and observed is None:
            excluded["unknown_date_and_observation"] += 1
            continue
        key = (raw["product_ref"], " ".join(body.casefold().split()))
        if key in seen:
            excluded["duplicate_body_within_product"] += 1
            continue
        seen.add(key)
        sample.append((raw, day))
    return sorted(sample, key=lambda p: (p[0]["product_ref"], p[0].get("source") or "",
                                         p[0].get("review_id") or "", p[0]["body"])), dict(excluded)


def _annotate(raw, day):
    matches = defaultdict(list)
    evidence = defaultdict(list)
    rating = _rating(raw.get("rating"))
    for sentence in sentences(raw["body"]):
        for aspect, label in tag_sentence(sentence, rating).items():
            matches[aspect].append(label)
            evidence[aspect].append(dict(review_evidence(raw, sentence), polarity=label))
    aspects = {}
    for a, labels in matches.items():
        label = merge_polarities(labels)
        example = next((e for e in evidence[a] if e["polarity"] == label), evidence[a][0])
        aspects[a] = (label, example)
    return {"ref": raw["product_ref"], "source": raw.get("source"), "day": day, "rating": rating,
            "evidence": review_evidence(raw), "aspects": aspects}


def _aspect_stats(reviews, validation):
    n_reviews = len(reviews)
    low = sum(1 for r in reviews if r["rating"] is not None and r["rating"] <= 2)
    counts = defaultdict(Counter)
    examples = defaultdict(lambda: defaultdict(list))
    low_examples = defaultdict(list)
    for r in reviews:
        for a, (label, quote) in r["aspects"].items():
            c = counts[a]
            c[label] += 1
            c["low"] += int(r["rating"] is not None and r["rating"] <= 2)
            examples[a][label].append(quote)
            if r["rating"] is not None and r["rating"] <= 2:
                low_examples[a].append(quote)

    result = {}
    for a in lexicon():
        c = counts[a]
        n_dir = c["pos"] + c["neg"]
        mentions = n_dir + c["neutral"] + c["mixed"]
        rate = _average(mentions, n_reviews)
        # Round-robin by class so a majority class can't hide the minority's evidence.
        groups = [examples[a][label] for label in ("neg", "pos", "mixed", "neutral")]
        examples_a = [g[j] for j in range(3) for g in groups if len(g) > j]
        validated = validation["version_matches"] and validation["aspects"][a]["enabled"]
        result[a] = {
            "mentions": mentions, "pos": c["pos"], "neg": c["neg"], "mixed": c["mixed"],
            "neutral": c["neutral"], "directional_n": n_dir, "nss": _average(c["pos"]-c["neg"], n_dir),
            "mention_rate": rate, "review_count": n_reviews, "low_rating_count": low,
            "low_rating_mentions": c["low"], "complaint_lift": c["low"]/low/rate if low and rate else None,
            "wilson": _wilson(c["pos"], n_dir), "validated": validated,
            "claim_eligible": bool(validated and n_dir >= 30), "evidence": _examples(examples_a),
            "low_rating_evidence": _examples(sorted(low_examples[a], key=lambda e: e["polarity"] != "neg")),
            "negative_evidence": _examples(e for e in low_examples[a] if e["polarity"] == "neg"),
        }
    return result


# Sizes are never converted between mass and volume or across pack configurations.
UNIT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(kg|gm|g|l|ml)\s*$", re.I)


def _quantity(value):
    m = UNIT.fullmatch(str(value or ""))
    if not m or float(m[1]) <= 0:
        return None
    magnitude = float(m[1])
    unit = m[2].lower()
    return (magnitude * 1000 if unit in ("kg", "l") else magnitude, "ml" if unit in ("ml", "l") else "g")


def _listing_size(product, listing):
    title = listing.get("title") or product.get("title") or ""
    counts = re.findall(r"\bpack of\s*(\d+)\b|\b(\d+)\s*[- ]?pack\b|\b(\d+)\s*[x×]\s*\d", title, re.I)
    if any(int(next(v for v in group if v)) > 1 for group in counts):
        return None
    if listing.get("size"):
        return _quantity(listing["size"])
    if listing.get("matched_variant_sku"):
        for v in product.get("variants", []):
            if v.get("sku") == listing["matched_variant_sku"]:
                return _quantity(v.get("size"))
        return None
    # A selected competitor is a single item with its own canonical marketplace URL.
    if product.get("url") and product["url"] == listing.get("url"):
        return _quantity(product.get("size"))
    variants = product.get("variants", [])
    variant_sizes = {_quantity(v.get("size")) for v in variants}
    if len(variant_sizes) == 1:
        return next(iter(variant_sizes))
    if not variants:
        return _quantity(product.get("size"))
    return None


def _variant_key(product, listing, size):
    variants = product.get("variants") or []
    specified = listing.get("matched_variant_sku")
    if specified:
        variant = next((v for v in variants if v.get("sku") == specified), None)
        if variant and (not listing.get("size") or _quantity(variant.get("size")) == size):
            return specified
        return None
    if not size:
        return None
    matches = [v.get("sku") for v in variants if _quantity(v.get("size")) == size]
    # Size alone resolves a variant only if no competing shade or flavour has that size.
    return matches[0] if len(matches) == 1 else None


def _series(report, products, as_of):
    listings = {(r["product_ref"], r["market"], r["external_id"]): r for r in report.get("listings", [])}
    histories = defaultdict(dict)
    for snap in report.get("listing_snapshots", []):
        ref = snap.get("product_ref")
        timestamp = snap.get("captured_at")
        day = utc_date(timestamp)
        if ref not in products or not day or day > as_of:
            continue
        key = (ref, snap.get("market"), snap.get("external_id"))
        try:
            instant = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            instant = instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None else instant.astimezone(timezone.utc)
        except ValueError:
            continue
        # Intra-day refreshes cannot manufacture a second independent day.
        previous = histories[key].get(day)
        if not previous or instant > previous[0]:
            histories[key][day] = (instant, snap)

    series = []
    for key, daily in sorted(histories.items()):
        ref, market, external_id = key
        listing = listings.get(key, {})
        samples = [(day, daily[day][1]) for day in sorted(daily)]
        latest_day, latest = samples[-1]
        price = _number(latest.get("price"))
        size = _listing_size(products[ref], listing)
        currency = latest.get("currency") or listing.get("currency") or products[ref].get("currency") or "INR"
        valid_price = price is not None and price > 0 and currency == "INR"

        # A parent PDP may repeat the same counts across several child packs or shades.
        rated = _rating(latest.get("rating")) if latest.get("rating_scope") != "parent_product" else None
        count = _number(latest.get("rating_count"))
        rating_n = int(count) if rated is not None and count and count > 0 and count.is_integer() else 0
        trajectory = []
        price_history = []
        for d, s in samples:
            value = _number(s.get("rating_count")) if s.get("rating_scope") != "parent_product" else None
            if value is not None and value >= 0 and value.is_integer():
                trajectory.append((d, int(value)))
            p, mrp = _number(s.get("price")), _number(s.get("mrp"))
            if p is not None and mrp and mrp >= p > 0:
                price_history.append({"date": d.isoformat(), "price": p, "mrp": mrp, "discount_depth": 1-p/mrp})

        velocity = None
        if len(trajectory) >= 2 and all(right[1] >= left[1] for left, right in zip(trajectory, trajectory[1:])):
            first, last = trajectory[0], trajectory[-1]
            days = (last[0]-first[0]).days
            velocity = {"from_date": first[0].isoformat(), "to_date": last[0].isoformat(),
                        "delta": last[1]-first[1], "days": days, "per_day": (last[1]-first[1])/days}
        depths = {item["date"]: item["discount_depth"] for item in price_history}
        previous = depths.get((as_of-timedelta(days=30)).isoformat())
        current = depths.get(as_of.isoformat())
        series.append({"ref": ref, "market": market, "external_id": external_id,
                       "url": latest.get("url") or listing.get("url"), "as_of": latest_day.isoformat(),
                       "rating": rated, "n": rating_n, "variant_sku": _variant_key(products[ref], listing, size),
                       "price": price if valid_price else None,
                       "unit": size[1] if size and valid_price else None,
                       "per_unit": price/size[0] if size and valid_price else None,
                       "discount_depth": depths.get(latest_day.isoformat()),
                       "discount_change_30d": current-previous if previous is not None and current is not None else None,
                       "price_history": price_history, "velocity": velocity})
    return series


def _rating_stats(reviews, series, priors):
    market = defaultdict(lambda: {"total": 0., "n": 0, "listings": 0, "evidence": []})
    for s in series:
        if not s["n"]:
            continue
        g = market[s["market"]]
        g["total"] += s["rating"]*s["n"]
        g["n"] += s["n"]
        g["listings"] += 1
        g["evidence"].append({k:s[k] for k in ("url", "ref", "external_id", "as_of", "rating", "n")})
    by_market = {key: {"mean": g["total"]/g["n"], "n": g["n"], "listings": g["listings"],
                       "evidence": g["evidence"]} for key, g in market.items()}
    variants = defaultdict(lambda: defaultdict(list))
    for s in series:
        if s["n"] and s["variant_sku"]:
            variants[s["variant_sku"]][s["market"]].append(s)
    by_variant = {}
    for sku, channels in variants.items():
        by_variant[sku] = {}
        for channel, observations in channels.items():
            count = sum(s["n"] for s in observations)
            by_variant[sku][channel] = {"n": count, "mean": sum(s["n"]*s["rating"] for s in observations)/count,
                                        "urls": [s["url"] for s in observations if s["url"]]}
    sample = [r["rating"] for r in reviews if r["rating"] is not None]
    total = sum(g["total"] for g in market.values())
    n = sum(g["n"] for g in market.values())
    basis = "listing_rating_counts" if n else "sampled_reviews"
    if not n:
        total, n = sum(sample), len(sample)
    prior = priors[basis]
    return {"mean": _average(total, n), "bayesian": (PRIOR_WEIGHT*prior+total)/(PRIOR_WEIGHT+n)
            if prior is not None and n else None, "prior_mean": prior, "prior_weight": PRIOR_WEIGHT, "n": n,
            "basis": basis, "by_market": by_market, "by_variant": by_variant, "sampled_rating_n": len(sample),
            "sampled_rating_mean": _average(sum(sample), len(sample))}


def _unit_prices(series):
    grouped = defaultdict(lambda: defaultdict(list))
    for s in series:
        if s["unit"]:
            grouped[s["unit"]][s["ref"]].append(s["per_unit"])
    return {unit: {ref: median(values) for ref, values in products.items()} for unit, products in grouped.items()}


def _stats(refs, reviews, series, priors, unit_medians, validation):
    monthly = Counter(r["day"].strftime("%Y-%m") for r in reviews if r["day"])
    velocities = [dict(s["velocity"], url=s["url"], product_ref=s["ref"], market=s["market"])
                  for s in series if s["velocity"]]
    price_by_unit = {}
    for unit, ref_prices in _unit_prices(series).items():
        price = median(ref_prices.values())
        base = unit_medians[unit]
        price_by_unit[unit] = {"index": price/base, "median_per_unit": price, "n": len(ref_prices),
                              "category_median_per_unit": base, "currency": "INR"}
    changes = [s["discount_change_30d"] for s in series if s["discount_change_30d"] is not None]
    depths = [s["discount_depth"] for s in series if s["discount_depth"] is not None]
    return {
        "product_count": len(refs), "review_count": len(reviews),
        "review_sources": dict(sorted(Counter(r["source"] for r in reviews).items())),
        "evidence": _examples(r["evidence"] for r in reviews),
        "rating": _rating_stats(reviews, series, priors),
        "price": {"by_unit": price_by_unit, "n": sum(s["price"] is not None for s in series),
                  "discount_depth": _median(depths), "discount_n": len(depths),
                  "discount_change_30d": _median(changes), "discount_change_30d_n": len(changes),
                  "listings": [{k:v for k,v in s.items() if k not in ("velocity", "rating", "n")} for s in series]},
        "velocity": {"per_day": sum(v["per_day"] for v in velocities) if velocities else None,
                     "n": len(velocities), "listings": velocities, "monthly": dict(sorted(monthly.items())),
                     "dated_reviews": sum(monthly.values()), "undated_reviews": len(reviews)-sum(monthly.values())},
        "aspects": _aspect_stats(reviews, validation),
    }


def build_metrics(raw_report, as_of: date):
    as_of = utc_date(as_of)
    if as_of is None:
        raise ValueError("as_of must be a calendar date")
    products = {p["product_ref"]: p for p in raw_report.get("products", []) if not p.get("is_combo")
                and (not utc_date(p.get("published_at")) or utc_date(p["published_at"]) <= as_of)}
    sample, excluded = _review_sample(raw_report, products, as_of)
    reviews = [_annotate(raw, day) for raw, day in sample]
    series = _series(raw_report, products, as_of)
    all_ratings = [r["rating"] for r in reviews if r["rating"] is not None]
    priors = {
        "listing_rating_counts": _average(sum(s["rating"]*s["n"] for s in series if s["n"]), sum(s["n"] for s in series)),
        "sampled_reviews": _average(sum(all_ratings), len(all_ratings)),
    }
    units = {u:median(refs.values()) for u, refs in _unit_prices(series).items()}
    validation = _validation()
    def stats_for(refs):
        return _stats(refs, [r for r in reviews if r["ref"] in refs], [s for s in series if s["ref"] in refs],
                      priors, units, validation)
    brands = defaultdict(set)
    for ref,p in products.items():
        brands[p["brand"]].add(ref)
    return {"as_of": as_of.isoformat(), "products": {ref:stats_for({ref}) for ref in sorted(products)},
            "brands": {b:stats_for(refs) for b, refs in sorted(brands.items())},
            "category": stats_for(set(products)), "excluded_reviews": excluded, "validation": validation,
            "method": {"rating": "Latest daily marketplace rating weighted by cumulative rating count. Explicit parent-product rating aggregates are excluded to avoid duplicating them across child SKUs. Sample-only fallback has its own category prior; compare within the same basis.",
                       "aspect": "One vote per sampled review and aspect. Mixed or neutral views contribute to mentions only. Wilson is a 95% interval on positive share among directional votes.",
                       "price": "INR per g or ml. Median latest comparable listing price per product, then category or brand median across products. Mass and volume are separate.",
                       "velocity": "Sum of comparable same-listing cumulative rating-count changes per day. Drops invalidate that listing trajectory. Monthly counts are dated sampled reviews."}}
