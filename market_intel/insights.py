"""Offline category insight report consumed by the UI and Part 3."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from .store import Store


def build_insights(db_path, catalog_path, category, as_of=None):
    from .catalog_history import catalog_context, latest_snapshot_date
    from .forecast import build_forecast
    from .gaps import build_gaps
    from .metrics import build_metrics, utc_date
    from .recommendations import build_recommendations
    from .swot import build_swot
    from .trends import build_trends

    if not Path(db_path).is_file():
        return None
    with closing(Store(db_path)) as store:
        raw = store.report(category)
    if raw is None:
        return None
    if not raw["competitor_set"] and all(p.get("is_combo") for p in raw["products"]):
        return None
    if as_of is None:
        dates = [utc_date(s.get("captured_at")) for s in raw["listing_snapshots"]]
        dates.append(latest_snapshot_date(catalog_path))
        dates = [d for d in dates if d is not None]
        if not dates:
            dates = [
                day
                for rows, field in (
                    (raw["products"], "published_at"),
                    (raw["reviews"], "observed_at"),
                    (raw["reviews"], "date"),
                    (raw["brand_signals"], "captured_at"),
                )
                for record in rows
                if (day := utc_date(record.get(field))) is not None
            ]
        if not dates:
            raise ValueError("An analysis date is required for undated data")
        as_of = max(dates)
    end = as_of.isoformat()

    def available(row, field):
        day = utc_date(row.get(field))
        return day is None or day <= as_of

    raw["products"] = [p for p in raw["products"] if available(p, "published_at")]
    eligible = {p["product_ref"] for p in raw["products"]}
    for key in ("listings", "listing_snapshots", "reviews", "competitor_set"):
        raw[key] = [r for r in raw[key] if r["product_ref"] in eligible]
    raw["listing_snapshots"] = [
        s for s in raw["listing_snapshots"] if available(s, "captured_at")
    ]
    raw["reviews"] = [
        r
        for r in raw["reviews"]
        if available(r, "date") and available(r, "observed_at")
    ]
    raw["brand_signals"] = [
        s for s in raw["brand_signals"] if available(s, "captured_at")
    ]
    raw["news_items"] = [
        s
        for s in raw["news_items"]
        if available(s, "date") and available(s, "observed_at")
    ]
    context = catalog_context(catalog_path, raw["category"], as_of)
    metrics = build_metrics(raw, as_of)
    trends = build_trends(raw, context, as_of)
    gaps = build_gaps(raw, metrics, context, as_of)
    swot = build_swot(raw, metrics, gaps, trends, as_of)
    return {
        "schema_version": 1,
        "category": raw["category"],
        "as_of": end,
        "scope": {
            "selected_competitors": raw["competitor_set"],
            "review_count": len(raw["reviews"]),
            "catalog_snapshot_coverage": context.get("coverage", []),
            "as_of_policy": "Analysis windows end on this day. Marketplace peer selection and product metadata reflect the stored Part 1 catalog.",
        },
        "metrics": metrics,
        "swot": swot,
        "gaps": gaps,
        "trends": trends,
        "forecast": build_forecast(raw, metrics, gaps, as_of),
        "recommendations": build_recommendations(swot, gaps, trends),
    }


def opportunity_overview(db_path, catalog_path, as_of=None):
    """Rank categories with measured opportunity factors and keep unsupported scores visible."""
    categories = []
    if Path(db_path).is_file():
        with closing(Store(db_path)) as store:
            categories = [
                row[0]
                for row in store.db.execute(
                    "SELECT DISTINCT category FROM product WHERE is_competitor=0 AND is_combo=0 ORDER BY category"
                )
            ]
    rows, ideas = [], {}
    for category in categories:
        report = build_insights(db_path, catalog_path, category, as_of)
        forecast = report["forecast"]
        score = forecast["opportunity_score"]
        rows.append(
            {
                "category": category,
                "as_of": report["as_of"],
                "opportunity_score": score,
                "forecast_growth": forecast["forecast_growth"],
                "score_factors": forecast["score_factors"],
                "n": forecast["n"],
                "reason": forecast.get("reason"),
                "swot_claims": {q: len(v) for q, v in report["swot"].items()},
                "recent_catalog_launches": len(report["trends"]["launches"]),
                "qualified_trends": len(report["trends"]["trending"]),
                "insights_path": f"/category/{quote(category, safe='')}/insights",
            }
        )
        for term in report["trends"]["trending"]:
            if term["missing_at_dot_key"] and score is not None:
                ideas.setdefault(term["term"], []).append((score, category, term["id"]))
    rows.sort(
        key=lambda row: (
            row["opportunity_score"] is None,
            -(row["opportunity_score"] or 0),
            row["category"],
        )
    )
    term_opportunities = []
    for term, options in sorted(ideas.items()):
        score, category, trend_id = min(options, key=lambda item: (-item[0], item[1]))
        term_opportunities.append(
            {
                "term": term,
                "category": category,
                "opportunity_score": score,
                "trend_id": trend_id,
            }
        )
    return {
        "categories": rows,
        "score_definition": "Forecast growth × (1 − Dot & Key share of observed review volume) × distinct gap count",
        "term_opportunities": term_opportunities,
    }
