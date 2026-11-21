"""Stable, server-resolved citations shared by Ask, dashboard cards and Studio briefs."""

from __future__ import annotations

from datetime import date
from urllib.parse import quote, urlencode

from .cache import report_for
from .catalog import competitors, launches


def cards(report):
    name, day = report["category"], report["as_of"]

    def card(key, title, kind, view="strategy", evidence=None, description=None):
        href = (
            "/?"
            + urlencode({"view": view, "category": name, "as_of": day})
            + "#"
            + quote(key, safe=":")
        )
        return {
            "id": key,
            "title": title,
            "type": kind,
            "category": name,
            "as_of": day,
            "view": view,
            "href": href,
            "evidence": evidence or [],
            "description": description,
        }

    for kind, rows in report["swot"].items():
        for r in rows:
            yield card(
                r["id"],
                r["title"],
                kind,
                evidence=r.get("evidence_quotes") or r.get("evidence_sources"),
                description=r.get("threshold"),
            )
    for section in ("whitespace", "category_pain", "unmet_needs"):
        for r in report["gaps"][section]:
            yield card(r["id"], r["title"], section, evidence=r.get("evidence"))
    for r in report["recommendations"]:
        yield card(
            r["id"],
            r["action"],
            "recommendation",
            evidence=r["trigger_ids"],
            description=r.get("trigger_threshold"),
        )
    rising_ids = {r["id"] for r in report["trends"]["trending"]}
    for r in report["trends"]["terms"]:
        rising = r["id"] in rising_ids
        title = ("Rising mentions of " if rising else "Tracked term: ") + r["term"]
        description = (
            f"{r['rising_signal_count']} independent signals meet the rising threshold."
            if rising
            else "This term has not met the cross-source threshold for a rising trend."
        )
        yield card(
            r["id"],
            title,
            "trend" if rising else "tracked_term",
            evidence=r.get("evidence"),
            description=description,
        )
    f = report["forecast"]
    share = f["score_factors"]["dk_share"]
    if share is not None:
        yield card(
            "review-share",
            f"Dot & Key accounts for {share:.1%} of observed {name.lower()} review volume across the tracked brands.",
            "review_share",
            "overview",
            description=f["score_factors"].get("share_scope"),
        )
    if f["opportunity_score"] is not None:
        yield card(
            "opportunity",
            f"{name} has an opportunity score of {f['opportunity_score']:.3f}.",
            "opportunity_score",
            "overview",
            description=f["method"].get("score_formula"),
        )
    growth = f["forecast_growth"]
    title = (
        f"The forecast projects {growth:+.1%} growth in sampled review activity."
        if growth is not None
        else "Review activity has insufficient history for a demand projection."
    )
    yield card(
        "forecast", title, "forecast", description=f.get("reason") or f.get("source")
    )
    own = report["metrics"]["brands"].get("Dot & Key", {})
    for key, r in own.get("aspects", {}).items():
        if r["mentions"]:
            yield card(
                "aspect:" + key,
                f"{key.replace('_', ' ').capitalize()} appears in {r['mentions']} Dot & Key reviews, with {r['neg']} negative mentions.",
                "aspect",
                "customers",
                r.get("negative_evidence") or r.get("evidence"),
            )
    for r in launches(report):
        yield card(
            r["id"],
            r["title"],
            "launch",
            "competitors",
            r.get("evidence_urls"),
            f"{r['brand']} catalog launch signal dated {r['date']}.",
        )


def competitor_cards(report):
    day = date.fromisoformat(report["as_of"])
    for r in competitors(report["category"], day)["competitors"]:
        ident = r["id"]
        href = (
            "/?"
            + urlencode(
                {"view": "competitors", "category": report["category"], "as_of": day}
            )
            + "#"
            + ident
        )
        desc = (
            f"Rank {r['rank']} in the sampled competitor set for {report['category']}."
        )
        yield {
            "id": ident,
            "title": r["title"],
            "type": "competitor",
            "view": "competitors",
            "category": report["category"],
            "as_of": str(day),
            "description": desc,
            "href": href,
            "evidence": [r["url"]] if r.get("url") else [],
        }


def resolve_evidence(category, as_of, id):
    day = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    report = report_for(category, day)
    source = competitor_cards(report) if id.startswith("competitor:") else cards(report)
    return next((r for r in source if r["id"] == id), None)
