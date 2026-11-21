"""Product, marketplace, customer and competitor observations for the market screens."""

from __future__ import annotations

import json
from statistics import median

from fastapi import HTTPException

from market_intel.metrics import utc_date

from .cache import category_name, database, latest_day, report_for


def records(db, sql, args=()):
    return [json.loads(row[0]) for row in db.execute(sql, args)]


def available(row, field, day):
    when = utc_date(row.get(field))
    return when is None or when <= day


def present_product(product):
    return {**product, "image": next(iter(product.get("images") or []), None)}


def products(category, query, day):
    day = day or latest_day()
    name = category_name(category) if category else None
    # Apply searchable predicates before loading the large description and image arrays.
    sql = """SELECT data FROM product WHERE is_competitor=0 AND is_combo=0 AND (? IS NULL OR category=?)
             AND (instr(lower(title), lower(?))>0 OR instr(lower(json_extract(data,'$.handle')),lower(?))>0)
             ORDER BY title"""
    with database() as db:
        rows = records(db, sql, (name, name, query.strip(), query.strip()))
    fields = (
        "handle",
        "product_ref",
        "category",
        "title",
        "image",
        "price",
        "mrp",
        "hero_ingredient",
        "spf",
        "size",
        "currency",
    )
    selected = [
        {key: present.get(key) for key in fields}
        for p in rows
        if available(p, "published_at", day)
        for present in [present_product(p)]
    ]
    return {"products": selected, "total": len(selected), "as_of": day.isoformat()}


def product_detail(handle, day):
    day = day or latest_day()
    with database() as db:
        db.execute("BEGIN")
        row = db.execute(
            "SELECT data FROM product WHERE is_competitor=0 AND json_extract(data,'$.handle')=?",
            (handle,),
        ).fetchone()
        if not row or not available(product := json.loads(row[0]), "published_at", day):
            raise HTTPException(404, "Unknown product at this date")
        ref = (product["product_ref"],)
        snapshots = records(
            db,
            "SELECT data FROM listing_snapshot WHERE product_ref=? AND date(captured_at)<=? ORDER BY julianday(captured_at)",
            (*ref, str(day)),
        )
        listings = records(
            db,
            "SELECT data FROM listing WHERE product_ref=? ORDER BY market,external_id",
            ref,
        )
        reviews = [
            {**json.loads(row["data"]), "search_id": "review-" + row["body_hash"]}
            for row in db.execute(
                "SELECT data, body_hash FROM review WHERE product_ref=? ORDER BY julianday(date) DESC,body_hash",
                ref,
            )
        ]
    latest = {(s["market"], s["external_id"]): s for s in snapshots}
    listings = [
        {**r, **latest.get((r["market"], r["external_id"]), {})}
        for r in listings
        if (r["market"], r["external_id"]) in latest
        or available(r, "discovered_at", day)
    ]
    reviews = [
        r
        for r in reviews
        if available(r, "date", day) and available(r, "observed_at", day)
    ]
    return {
        "product": present_product(product),
        "as_of": str(day),
        "listings": listings,
        "snapshots": snapshots,
        "reviews": reviews,
    }


def aspect_values(stats):
    return {key: value["nss"] for key, value in stats.get("aspects", {}).items()}


def competitors(category, day):
    report = report_for(category, day)
    name = report["category"]
    day = utc_date(report["as_of"])
    with database() as db:
        titles = {
            r["product_ref"]: r
            for r in records(
                db,
                """SELECT data FROM product
            WHERE product_ref IN (SELECT product_ref FROM competitor_set WHERE category=?)""",
                (name,),
            )
        }
        signals = records(
            db,
            """SELECT data FROM brand_signal WHERE brand IN (SELECT p.brand FROM product p
            JOIN competitor_set c USING(product_ref) WHERE c.category=?) AND date(captured_at)<=?
            ORDER BY julianday(captured_at) DESC,brand""",
            (name, str(day)),
        )
    rankings = []
    for rank in report["scope"]["selected_competitors"]:
        ref = rank["product_ref"]
        p = titles.get(ref)
        stats = report["metrics"]["products"].get(ref)
        if not p or not stats:
            continue
        prices = [
            s["price"] for s in stats["price"]["listings"] if s["price"] is not None
        ]
        rankings.append(
            {
                **rank,
                "id": "competitor:" + str(rank["rank"]),
                "title": p["title"],
                "brand": p["brand"],
                "url": p.get("url"),
                "rating": stats["rating"]["mean"],
                "price": median(prices) if prices else None,
                "review_count": stats["review_count"],
                "aspects": aspect_values(stats),
            }
        )
    return {
        "category": name,
        "as_of": str(day),
        "competitors": rankings,
        "brand_signals": signals,
        "own_aspects": aspect_values(report["metrics"]["brands"].get("Dot & Key", {})),
    }


def launches(report):
    return [
        {**r, "id": "launch:" + r["product_ref"]} for r in report["trends"]["launches"]
    ]
