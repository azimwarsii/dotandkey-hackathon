"""Deterministic SWOT comparisons against the category's selected competitor brands."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
from math import isclose, isfinite, log
from statistics import median

OWN = "Dot & Key"
QUADRANTS = ("strength", "weakness", "opportunity", "threat")


def number(value):
    return type(value) in (int, float) and isfinite(value)


def make_id(*parts):
    return sha256("|".join(map(str, parts)).encode()).hexdigest()[:14]


def _quotes(*groups, polarity=None):
    selected = []
    # Round robin preserves both sides of a comparison when evidence is available.
    pools = [
        [
            r
            for r in group
            if r.get("quote")
            and (not polarity or r.get("polarity") in (polarity, None))
        ]
        for group in groups
    ]
    for i in range(max(map(len, pools), default=0)):
        for pool in pools:
            if i < len(pool) and pool[i]["quote"] not in {r["quote"] for r in selected}:
                selected.append(pool[i])
                if len(selected) == 3:
                    return selected
    return selected


def _rating(stats):
    return stats.get("rating", {}).get("bayesian")


def _utc_timestamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _marketplace_discounts(raw, peer_refs, as_of):
    start = as_of - timedelta(days=30)
    listings = {
        (r.get("product_ref"), r.get("market"), r.get("external_id")): r
        for r in raw["listings"]
    }
    daily = defaultdict(dict)
    for sample in raw.get("listing_snapshots", []):
        key = (
            sample.get("product_ref"),
            sample.get("market"),
            sample.get("external_id"),
        )
        if key[0] not in peer_refs or not all(key):
            continue
        stamp = _utc_timestamp(sample.get("captured_at"))
        if stamp and stamp.date() in (start, as_of):
            prior = daily[key].get(stamp.date())
            if prior is None or stamp > prior[0]:
                daily[key][stamp.date()] = (stamp, sample)
    for key, observations in sorted(daily.items()):
        if start not in observations or as_of not in observations:
            continue
        listing = listings.get(key, {})
        observations = [observations[start][1], observations[as_of][1]]
        points = []
        for sample in observations:
            price, mrp = sample.get("price"), sample.get("mrp")
            url = sample.get("url") or listing.get("url")
            if not (number(price) and number(mrp) and 0 < price <= mrp and url):
                break
            depth = 1 - Fraction(str(price)) / Fraction(str(mrp))
            points.append(
                (
                    depth,
                    {
                        "captured_at": sample["captured_at"],
                        "url": url,
                        "price": price,
                        "mrp": mrp,
                        "currency": sample.get("currency")
                        or listing.get("currency")
                        or "INR",
                        "discount_depth": float(depth),
                    },
                )
            )
        if len(points) != 2 or points[0][1]["currency"] != points[1][1]["currency"]:
            continue
        delta = points[1][0] - points[0][0]
        if delta >= Fraction(1, 10):
            yield {
                "product_ref": key[0],
                "market": key[1],
                "external_id": key[2],
                "from_date": str(start),
                "to_date": str(as_of),
                "before": points[0][1],
                "after": points[1][1],
                "discount_change_30d": float(delta),
            }


def build_swot(raw, metrics, gaps, trends, as_of):
    products = {p["product_ref"]: p for p in raw["products"]}
    peers = [
        products[r["product_ref"]]["brand"]
        for r in raw["competitor_set"]
        if r["product_ref"] in products
    ]
    brands = metrics["brands"]
    own = brands.get(OWN, {})
    others = {b: brands[b] for b in peers if b in brands}
    rows = []

    def emit(
        quadrant,
        rule,
        subject,
        title,
        values,
        threshold,
        n,
        effect,
        quotes=(),
        sources=(),
        related=(),
    ):
        if n <= 0:
            return
        rows.append(
            {
                "id": rule + "-" + make_id(raw["category"], subject),
                "rule": rule,
                "quadrant": quadrant,
                "subject": subject,
                "title": title,
                "metric_values": values,
                "threshold": threshold,
                "n": n,
                "effect_size": round(float(effect), 6),
                "rank_score": round(abs(float(effect)) * log(n), 6),
                "evidence_quotes": list(quotes),
                "evidence_sources": sorted({s for s in sources if s}),
                "related_ids": list(related),
            }
        )

    listings_by_ref = defaultdict(list)
    for row in raw["listings"]:
        listings_by_ref[row["product_ref"]].append(row["url"])
    links = {
        brand: sorted(
            {
                url
                for ref, p in products.items()
                if p["brand"] == brand
                for url in listings_by_ref[ref]
            }
        )
        for brand in [OWN, *peers]
    }

    for aspect, obs in sorted(own.get("aspects", {}).items()):
        name = aspect.replace("_", " ")
        reference = {
            brand: stats["aspects"][aspect]
            for brand, stats in others.items()
            if stats.get("aspects", {}).get(aspect, {}).get("claim_eligible")
        }
        if obs.get("claim_eligible") and len(reference) >= 3:
            baseline = median(v["nss"] for v in reference.values())
            difference = obs["nss"] - baseline
            low, high = obs["wilson"]
            peer_share = (1 + baseline) / 2
            values = {
                "aspect": aspect,
                "own_nss": obs["nss"],
                "peer_median_nss": baseline,
                "peer_nss": {b: v["nss"] for b, v in reference.items()},
                "own_positive_share_interval": [low, high],
                "mention_rate": obs["mention_rate"],
            }
            nearest = min(
                reference.values(), key=lambda point: abs(point["nss"] - baseline)
            )
            comparison = _quotes(obs.get("evidence", []), nearest.get("evidence", []))
            if difference >= 0.15 and low > peer_share:
                emit(
                    "strength",
                    "aspect_advantage",
                    aspect,
                    f"Stronger sentiment on {name}",
                    values,
                    "NSS lead ≥ 0.15; lower Wilson bound exceeds peer positive share",
                    obs["directional_n"],
                    difference,
                    comparison,
                )
                weak_peers = {b: v for b, v in reference.items() if v["nss"] < 0}
                if weak_peers:
                    emit(
                        "opportunity",
                        "messaging_advantage",
                        aspect,
                        f"Test messaging about {name}",
                        dict(values, negative_peers=sorted(weak_peers)),
                        "Eligible strength and a negative-NSS peer",
                        obs["directional_n"],
                        difference,
                        _quotes(
                            obs.get("evidence", []),
                            next(iter(weak_peers.values())).get("evidence", []),
                        ),
                    )
            elif difference <= -0.15 and high < peer_share:
                emit(
                    "weakness",
                    "aspect_disadvantage",
                    aspect,
                    f"Weaker sentiment on {name}",
                    values,
                    "NSS deficit ≥ 0.15; upper Wilson bound below peer positive share",
                    obs["directional_n"],
                    -difference,
                    comparison,
                )
        lift = obs.get("complaint_lift")
        if (
            obs.get("validated")
            and obs["mentions"] >= 30
            and number(lift)
            and lift >= 2
            and obs["mention_rate"] >= 0.05
            and obs.get("low_rating_mentions", 0) > 0
        ):
            emit(
                "weakness",
                "complaint_lift",
                aspect,
                f"{name.capitalize()} appears disproportionately in low-star reviews",
                {
                    "aspect": aspect,
                    "complaint_lift": lift,
                    "mention_rate": obs["mention_rate"],
                    "low_rating_mentions": obs["low_rating_mentions"],
                    "low_rating_count": obs["low_rating_count"],
                },
                "Lift ≥ 2 and mention rate ≥ 5%, with ≥ 30 mentions",
                obs["mentions"],
                lift - 1,
                _quotes(obs.get("low_rating_evidence", [])),
            )
        negatives = {b: v for b, v in reference.items() if v["nss"] < 0}
        if len(negatives) >= 4:
            emit(
                "opportunity",
                "peer_pain",
                aspect,
                f"Competitor reviews flag {name}",
                {
                    "aspect": aspect,
                    "negative_peer_nss": {b: v["nss"] for b, v in negatives.items()},
                },
                "At least four of five peers have eligible negative NSS",
                sum(v["directional_n"] for v in negatives.values()),
                -median(v["nss"] for v in negatives.values()),
                _quotes(*(v.get("evidence", []) for v in negatives.values())),
            )

    own_rating = _rating(own)
    ratings = {
        b: _rating(s)
        for b, s in others.items()
        if number(_rating(s))
        and s["rating"].get("basis") == own.get("rating", {}).get("basis")
    }
    if number(own_rating) and len(ratings) == 5:
        rank = 1 + sum(value > own_rating for value in ratings.values())
        peer_mid = median(ratings.values())
        if rank <= 2:
            emit(
                "strength",
                "top_rating",
                OWN,
                f"Dot & Key ranks {rank} of 6 on Bayesian rating",
                {
                    "rank": rank,
                    "bayesian_rating": own_rating,
                    "peer_ratings": ratings,
                    "ties_share_rank": True,
                },
                "Rank 1 or 2 across all six brands",
                own["rating"]["n"],
                abs(own_rating - peer_mid),
                sources=[url for brand in (OWN, *ratings) for url in links[brand]],
            )
        for unit, item in own.get("price", {}).get("by_unit", {}).items():
            idx = item.get("index")
            if not number(idx):
                continue
            group = {
                "unit": unit,
                "price_index": idx,
                "bayesian_rating": own_rating,
                "peer_median_rating": peer_mid,
            }
            if idx <= 0.9 and own_rating >= peer_mid:
                emit(
                    "strength",
                    "value_leader",
                    unit,
                    f"Value pricing in packs measured in {unit}",
                    group,
                    "Price index ≤ 0.9 and rating ≥ peer median",
                    item["n"],
                    1 - idx,
                    sources=links[OWN],
                )
            if idx > 1.2 and own_rating <= peer_mid:
                emit(
                    "weakness",
                    "premium_price",
                    unit,
                    f"Premium pricing in packs measured in {unit}",
                    group,
                    "Price index > 1.2 and rating ≤ peer median",
                    item["n"],
                    idx - 1.0,
                    sources=links[OWN],
                )
            for brand, rating in ratings.items():
                rival = others[brand]["price"]["by_unit"].get(unit, {})
                peer_index = rival.get("index")
                if number(peer_index) and rating > own_rating and peer_index <= idx:
                    emit(
                        "threat",
                        "better_value",
                        f"{brand}/{unit}",
                        f"{brand} scores higher at a comparable or lower price per {unit}",
                        dict(
                            group,
                            competitor=brand,
                            peer_rating=rating,
                            peer_index=peer_index,
                        ),
                        "Higher Bayesian rating with equal or lower unit-price index",
                        others[brand]["rating"]["n"],
                        (rating - own_rating) / 5 + (idx - peer_index),
                        sources=links[brand] + links[OWN],
                    )
    velocities = {
        b: s["velocity"]["per_day"]
        for b, s in others.items()
        if number(s.get("velocity", {}).get("per_day"))
    }
    speed = own.get("velocity", {}).get("per_day")
    if (
        len(velocities) == 5
        and number(speed)
        and speed > max(velocities.values())
        and speed > 0
    ):
        emit(
            "strength",
            "fastest_velocity",
            OWN,
            "Dot & Key has the fastest observed rating-count growth",
            {"per_day": speed, "peer_per_day": velocities},
            "Positive growth exceeding all five peers",
            own["velocity"]["n"],
            (speed - max(velocities.values())) / speed,
            sources=links[OWN],
        )

    for ref, stats in metrics["products"].items():
        if products[ref]["brand"] != OWN:
            continue
        for sku, by_market in stats["rating"].get("by_variant", {}).items():
            channels = [
                (market, v) for market, v in by_market.items() if number(v.get("mean"))
            ]
            if len(channels) < 2:
                continue
            lo = min(channels, key=lambda item: item[1]["mean"])
            hi = max(channels, key=lambda item: item[1]["mean"])
            diff = round(hi[1]["mean"] - lo[1]["mean"], 6)
            if diff >= 0.3:
                emit(
                    "weakness",
                    "channel_gap",
                    f"{ref}/{sku}",
                    f"{products[ref]['title']} rates lower on {lo[0]}",
                    {
                        "product_ref": ref,
                        "variant_sku": sku,
                        "lower_market": lo[0],
                        "higher_market": hi[0],
                        "rating_gap": diff,
                        "ratings": {k: v["mean"] for k, v in channels},
                    },
                    "Same SKU differs by ≥ 0.3 stars",
                    sum(v["n"] for _, v in channels),
                    diff,
                    sources=[url for _, v in channels for url in v.get("urls", [])],
                )

    for gap in gaps.get("whitespace", []):
        emit(
            "opportunity",
            "whitespace",
            gap["id"],
            gap["title"],
            gap["metric_values"],
            gap["threshold"],
            gap["n"],
            gap.get("effect_size", 1),
            quotes=_quotes([e for e in gap.get("evidence", []) if isinstance(e, dict)]),
            sources=[
                e.get("url") for e in gap.get("evidence", []) if isinstance(e, dict)
            ],
            related=[gap["id"]],
        )
    for term in trends.get("trending", []):
        if term["missing_at_dot_key"]:
            emit(
                "opportunity",
                "missing_trend",
                term["term"],
                f"Evaluate {term['term']} in {raw['category']}",
                {"term": term["term"], "signals": term.get("signals", {})},
                "Growth ≥ 1.5 on two supported signals and absent in own category catalog",
                term["n"],
                term["growth"],
                quotes=_quotes(term.get("evidence", [])),
                sources=[e.get("url") for e in term.get("evidence", [])],
                related=[term.get("id", term["term"])],
            )

    launches = defaultdict(list)
    for row in trends.get("launches", []):
        if (
            row.get("category") == raw["category"]
            and row.get("date")
            and (as_of - timedelta(days=89)).isoformat()
            <= row["date"][:10]
            <= as_of.isoformat()
        ):
            launches[row["brand"]].append(row)
    for brand, entries in sorted(launches.items()):
        noun = "launch" if len(entries) == 1 else "launches"
        emit(
            "threat",
            "recent_launch",
            brand,
            f"{brand} has {len(entries)} recent {raw['category'].lower()} catalog {noun}",
            {
                "brand": brand,
                "launches": [
                    {
                        "title": e["title"],
                        "date": e["date"],
                        "basis": e["launch_basis"],
                        "product_ref": e["product_ref"],
                    }
                    for e in entries
                ],
            },
            "Newly observed or created on baseline within 90 days",
            len(entries),
            len(entries),
            sources=[e["url"] for e in entries],
        )

    peer_refs = {ref: p["brand"] for ref, p in products.items() if p["brand"] in others}
    for comparison in _marketplace_discounts(raw, peer_refs, as_of):
        ref, market, external_id = (
            comparison["product_ref"],
            comparison["market"],
            comparison["external_id"],
        )
        emit(
            "threat",
            "discount_pressure",
            f"{ref}/{market}/{external_id}",
            f"{peer_refs[ref]} increased its {market} discount",
            comparison,
            "Same listing's discount depth up ≥ 10 percentage points in 30 days",
            2,
            comparison["discount_change_30d"],
            sources=[comparison["before"]["url"], comparison["after"]["url"]],
        )
    for row in trends.get("price_changes", []):
        change = row.get("discount_change_30d")
        if number(change) and (
            change >= 0.1 or isclose(change, 0.1, rel_tol=0, abs_tol=1e-12)
        ):
            emit(
                "threat",
                "storefront_discount",
                f"{row['product_ref']}/{row['variant_id']}",
                f"{row['brand']} increased the discount on {row['title']}",
                row,
                "Same variant's discount depth up ≥ 10 percentage points in 30 days",
                2,
                change,
                sources=[row["url"]],
            )
    latest = {}
    for s in raw["brand_signals"]:
        if s.get("source") != "crustdata_company" or s["brand"] not in others:
            continue
        captured = _utc_timestamp(s.get("captured_at"))
        if captured and captured.date() <= as_of:
            previous = latest.get(s["brand"])
            if previous is None or captured > previous[0]:
                latest[s["brand"]] = (captured, s)
    for brand, (_, s) in sorted(latest.items()):
        for metric, growth in _company_growth(s).items():
            if growth >= 20:
                source = (
                    s.get("source_url") or "https://api.crustdata.com/company/enrich"
                )
                emit(
                    "threat",
                    "brand_momentum",
                    f"{brand}/{metric}",
                    f"{brand} shows {metric} growth",
                    {
                        "brand": brand,
                        "metric": metric,
                        "qoq_percent": growth,
                        "source": "crustdata_company",
                        "observed_at": s.get("captured_at"),
                    },
                    "Reported quarterly growth ≥ 20%",
                    1,
                    growth / 100,
                    sources=[source],
                )

    return {
        q: sorted(
            (r for r in rows if r["quadrant"] == q),
            key=lambda r: (-r["rank_score"], -r["effect_size"], r["id"]),
        )[:5]
        for q in QUADRANTS
    }


def _company_growth(signal):
    result = {}
    for metric, group in (
        ("followers", "followers"),
        ("traffic", "web_traffic"),
        ("hiring", "hiring"),
    ):
        values = signal.get(group)
        if not isinstance(values, dict):
            continue
        # Parent-company headcount/followers cannot be assigned to one child brand.
        if signal.get("entity_scope") in {
            "parent_company",
            "brand_family",
            "global_brand",
            "us_brand",
        }:
            continue
        growth = values.get("qoq_percent")
        if metric == "traffic":
            host = str(signal.get("domain") or "").lower().removeprefix("www.")
            traffic = (values.get("domain_traffic") or {}).get(host) or {}
            if number(traffic.get("qoq_pct")):
                growth = traffic["qoq_pct"]
        if (
            metric == "traffic"
            and not number(growth)
            and number(values.get("quarterly_growth"))
        ):
            growth = values["quarterly_growth"] * 100
        if metric == "hiring" and isinstance(
            values.get("openings_growth_percent"), dict
        ):
            growth = values["openings_growth_percent"].get("qoq")
        if number(growth):
            result[metric] = growth
    return result
