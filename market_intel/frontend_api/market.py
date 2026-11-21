"""A compact dashboard response; the large evidence arrays belong to detail views."""

from __future__ import annotations

from datetime import timedelta
from functools import lru_cache

from fastapi import HTTPException

from .cache import (
    cached_report,
    categories,
    category_name,
    database,
    latest_day,
    signature,
)
from .evidence import cards


def weekly_series(report, day):
    start = day - timedelta(days=89)

    def week(d):
        return d - timedelta(days=d.weekday())

    weeks = []
    cursor = week(start)
    while cursor <= day:
        weeks.append(str(cursor))
        cursor += timedelta(weeks=1)
    reviews = {
        k: {
            "week": k,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "unrated": 0,
            "total": 0,
        }
        for k in weeks
    }
    launches = {k: {"week": k, "total": 0} for k in weeks}
    with database() as db:
        rows = db.execute(
            """SELECT date(r.date) AS day,r.rating FROM review r JOIN product p USING(product_ref)
            WHERE p.is_combo=0 AND (p.is_competitor=0 AND p.category=? OR p.product_ref IN
              (SELECT product_ref FROM competitor_set WHERE category=?))
            AND date(r.date) BETWEEN ? AND ?
            AND COALESCE(date(json_extract(r.data,'$.observed_at')),?)<=?
            AND COALESCE(date(json_extract(p.data,'$.published_at')),?)<=?""",
            (
                report["category"],
                report["category"],
                str(start),
                str(day),
                str(day),
                str(day),
                str(day),
                str(day),
            ),
        )
        for when, rating in rows:
            bucket = reviews[str(week(day.fromisoformat(when)))]
            label = (
                "unrated"
                if rating is None
                else "positive"
                if rating >= 4
                else "negative"
                if rating <= 2
                else "neutral"
            )
            bucket[label] += 1
            bucket["total"] += 1
    for row in report["trends"]["launches"]:
        when = day.fromisoformat(row["date"])
        if start <= when <= day:
            launches[str(week(when))]["total"] += 1
    return list(reviews.values()), list(launches.values())


@lru_cache(maxsize=128)
def _overview(name, day, compare, database_signature):
    summary = [cached_report(c, day, index_only=True) for c in categories()]
    summary.sort(
        key=lambda r: (
            r["opportunity_score"] is None,
            -(r["opportunity_score"] or 0),
            r["category"],
        )
    )
    report = cached_report(name, day)
    forecast = report["forecast"]
    factors = forecast["score_factors"]
    value = factors["dk_share"]
    activity_field = (
        "rating_increment" if forecast["evidence"]["rating_panel"] else "dated_reviews"
    )
    previous = cached_report(name, compare, index_only=True)["dk_share"]
    delta = value - previous if value is not None and previous is not None else None
    own = report["metrics"]["brands"].get("Dot & Key", {})
    ratings = own.get("rating", {}).get("by_market", {})
    markets = [
        {
            "market": market,
            "rating": ratings.get(market, {}).get("mean"),
            "rating_count": ratings.get(market, {}).get("n"),
            "review_volume": own.get("review_sources", {}).get(market, 0),
            "volume_basis": "collected_review_texts",
        }
        for market in ("amazon", "flipkart", "nykaa")
    ]
    reviews, launches = weekly_series(report, day)
    all_cards = list(cards(report))
    recommendation = next(iter(report["recommendations"]), None)
    priority = None
    if recommendation:
        triggers = recommendation.get("trigger_ids", [])
        signal = next((r for r in all_cards if r["id"] in triggers), None)
        priority = {
            "id": recommendation["id"],
            "title": recommendation["action"],
            "source": {k: signal[k] for k in ("id", "view", "title")}
            if signal
            else None,
        }
    picks = []
    for kinds in [
        ("strength",),
        ("whitespace", "category_pain", "unmet_needs"),
        ("recommendation",),
    ]:
        choice = next((r for r in all_cards if r["type"] in kinds), None)
        if choice:
            picks.append(choice)
    for kind in ("threat", "weakness", "trend", "aspect", "forecast"):
        if len(picks) >= 3:
            break
        other = next((r for r in all_cards if r["type"] == kind), None)
        if other:
            picks.append(other)
    insights = [
        {k: choice[k] for k in ("id", "type", "title", "href")} for choice in picks
    ]
    return {
        "category": name,
        "as_of": str(day),
        "compare": str(compare),
        "categories": summary,
        "gap_count": factors["gap_count"],
        "priority": priority,
        "review_share": {
            "value": value,
            "previous": previous,
            "delta": delta,
            "markets": markets,
            "scope": factors["share_scope"],
            "source": factors["share_source"],
            "dk_review_volume": factors["dk_review_volume"],
            "top_six_review_volume": factors["top_six_review_volume"],
            "marketplaces": sorted(
                {r["market"] for r in factors["share_observations"]}
            ),
        },
        "demand": {
            "series": [
                {
                    "month": r["month"],
                    "index": r.get("index"),
                    "activity": r[activity_field],
                }
                for r in forecast["series"]
            ],
            "projection": forecast["projection"],
            "forecast_growth": forecast["forecast_growth"],
            "status": forecast["status"],
            "observations": forecast["n"],
            "source": forecast["source"],
            "baseline": forecast.get("baseline"),
            "activity_unit": "ratings"
            if activity_field == "rating_increment"
            else "reviews",
        },
        "review_velocity": reviews,
        "launch_velocity": launches,
        "insights": insights,
    }


def overview(category, day=None, compare=None):
    day = day or latest_day()
    compare = compare or day - timedelta(days=30)
    if compare > day:
        raise HTTPException(
            422, "Comparison date must be on or before the analysis date"
        )
    return _overview(category_name(category), day, compare, tuple(signature()))
