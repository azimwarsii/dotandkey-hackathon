"""Command line entry point for collection, probe runs and Part 2 exports."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import date, datetime
import json
import logging
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

from .client import Client, SourceUnavailable
from .store import Store


def crawl(client, store, args):
    from .catalog import collect_catalog
    from .competitors import collect_signals, select_competitors
    from .marketplaces import DOMAINS, collect_listings, discover, load_overrides, resolve_listing_conflicts
    from .reviews import collect_judgeme, collect_reddit

    def attempt(operation, target, fn, *params):
        try:
            return fn(*params)
        except (SourceUnavailable, ValueError, KeyError, IndexError) as exc:
            store.log(target, "unavailable", detail=f"{operation}: {exc}")
            return None

    if client.has_crustdata and args.stage != "first-party":
        attempt("account permissions", "/account/endpoints", client.permissions)
    overrides = load_overrides(args.overrides) if args.overrides else None
    if args.stage in ("all", "first-party"):
        store.save_catalog(collect_catalog(client))
    products = store.catalog()
    singles = [p for p in products if not p["is_combo"]]
    if args.category:
        singles = [p for p in singles if p["category"].casefold() == args.category.casefold()]
    if not singles:
        raise ValueError("No matching singles in the catalog. Run the first-party stage to populate SQLite.")
    cats = sorted({p["category"] for p in singles}, key=lambda c: (c.casefold() != "sunscreen", c))
    seen_brands = set()
    for category in cats:
        print(f"Collecting {category}", flush=True)
        own = [p for p in singles if p["category"] == category]
        if args.stage in ("all", "first-party"):
            for p in own:
                if args.judgeme_pages:
                    reviews = attempt("Judge.me", p["product_ref"], collect_judgeme, client, p, args.judgeme_pages)
                    store.save_reviews(reviews or [])
        if args.stage == "first-party":
            continue

        selected = attempt("competitor selection", category, select_competitors, client, category, own)
        if selected:
            store.save_selection(category, selected)
        else:
            store.log(category, "no_competitors_returned")
        targets = [(p, None) for p in own] + [(p, listing) for p, listing, _, _ in (selected or [])]
        listings = []
        for p, matched in targets:
            for market in DOMAINS:
                if matched and matched["market"] == market:
                    row = matched
                else:
                    keyed = client.has_crustdata
                    row = attempt("listing discovery", p["product_ref"], discover, client, p, market, overrides)
                    if keyed and not client.has_crustdata and not row:
                        row = attempt("public discovery", p["product_ref"], discover, client, p, market, overrides)
                if row:
                    listings.append(row)
                else:
                    store.log(p["product_ref"], "no_listing", detail=market)
            if client.has_crustdata and args.reddit_threads:
                store.save_reviews(attempt("Reddit", p["product_ref"], collect_reddit, client, p,
                                           args.reddit_threads) or [])
        listings = resolve_listing_conflicts(listings)
        for row in listings:
            store.save_listing(row)
        for i in range(0, len(listings), 10):
            batch = listings[i:i + 10]
            try:
                for row, snapshot, reviews in collect_listings(client, batch, args.review_pages):
                    store.save_listing(row, snapshot, reviews)
            except SourceUnavailable as exc:
                store.log(category, "batch_unavailable", detail=str(exc))
        for p, _, _, _ in selected or []:
            brand = p["brand"]
            if brand.casefold() not in seen_brands:
                result = attempt("brand signals", brand, collect_signals, client, brand)
                if result:
                    store.save_signals(brand, *result)
                seen_brands.add(brand.casefold())
        print(f"{category}: {len(own)} catalog products, {len(listings)} matched listings, "
              f"{len(selected or [])} ranked competitors", flush=True)


def spike(client, public=False):
    from .competitors import parse_category_page
    from .marketplaces import SPIKE_URLS, parse_listing

    if not public and not client.has_crustdata:
        raise SourceUnavailable("The Crustdata spike needs CRUSTDATA_API_KEY in .env. Use --public to probe the direct sources.")
    result = {"provider": "public" if public else "crustdata", "pages": {}}
    if public:
        url = "https://www.amazon.in/s?k=Dot+%26+Key+sunscreen"
        try:
            matches = parse_category_page(client.get(url), "amazon", url)
            result["amazon_search"] = {"result_count": len(matches), "url": url}
        except SourceUnavailable as exc:
            result["amazon_search"] = {"url": url, "error": str(exc)}
    else:
        account = client.permissions()
        paths = {"/web/search/live", "/web/enrich/live", "/company/enrich"}
        result["account_endpoints"] = {
            "api_version": account.get("api_version"),
            "endpoints": [r for r in account.get("endpoints", []) if r.get("path") in paths],
        }
        matches = client.search("Dot & Key sunscreen SPF 50", site="amazon.in")
        result["amazon_search"] = {"result_count": len(matches), "sample": matches[:1]}
    for kind, url in SPIKE_URLS.items():
        for human_mode in ((False, True) if kind == "nykaa" and not public else (False,)):
            page = {"url": url}
            try:
                html = client.get(url) if public else client.enrich([url], human_mode=human_mode).get(url, "")
                snapshot, reviews = parse_listing(kind.split("_")[0], html, "probe") if html else ({}, [])
                page.update(bytes=len(html.encode()), parsed_fields=sorted(snapshot), reviews=len(reviews),
                            observed_at=client.observations.get(url))
            except SourceUnavailable as exc:
                page["error"] = str(exc)
            result["pages"][f"{kind}-{'human' if human_mode else 'standard'}"] = page
    return result


def main(argv=None):
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("MARKET_INTEL_DB", "data/market-intel.sqlite3"))
    parser.add_argument("--cache", default="data/cache")
    parser.add_argument("--catalog-db", default=os.getenv("COMPETITOR_CATALOG_DB", "data/competitor-catalogs.sqlite3"))
    commands = parser.add_subparsers(dest="cmd", required=True)
    run = commands.add_parser("crawl")
    run.add_argument("--category")
    run.add_argument("--stage", choices=["all", "first-party", "market"], default="all")
    run.add_argument("--judgeme-pages", type=int, default=2)
    run.add_argument("--reddit-threads", type=int, default=1)
    run.add_argument("--review-pages", type=int, choices=range(6), default=2)
    run.add_argument("--overrides", help="CSV of product_ref,market,url")
    run.add_argument("--refresh", action="store_true", help="Refresh cached entries once per run")
    probe = commands.add_parser("spike")
    probe.add_argument("--output", type=Path)
    probe.add_argument("--public", action="store_true", help="Use direct public HTTP for the spike")
    report = commands.add_parser("report")
    report.add_argument("category")
    report.add_argument("--output", type=Path)
    insights = commands.add_parser("insights", help="Generate the deterministic Part 2 report")
    insights.add_argument("category")
    insights.add_argument("--as-of", type=date.fromisoformat, help="Window end date (YYYY-MM-DD)")
    insights.add_argument("--output", type=Path)
    overview = commands.add_parser("opportunities", help="Compare category-level demand projections and opportunities")
    overview.add_argument("--as-of", type=date.fromisoformat)
    overview.add_argument("--output", type=Path)
    catalogs = commands.add_parser("catalog-snapshot", help="Collect one daily snapshot of the nine competitor catalogs")
    catalogs.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "crawl" and min(args.judgeme_pages, args.reddit_threads) < 0:
        parser.error("Page limits must be nonnegative")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if args.cmd == "opportunities":
        from .insights import opportunity_overview
        write_output(opportunity_overview(args.db, args.catalog_db, args.as_of), args.output)
        return
    if args.cmd == "insights":
        from .insights import build_insights
        value = build_insights(args.db, args.catalog_db, args.category, args.as_of)
        if value is None:
            parser.error("Unknown insight category")
        write_output(value, args.output)
        return
    with closing(Store(args.db)) as store, closing(Client(args.cache, store.log,
                                               refresh=getattr(args, "refresh", args.cmd in {"spike","catalog-snapshot"}))) as client:
        if args.cmd == "catalog-snapshot":
            from .catalog_history import IST, snapshot_asins, snapshot_catalogs
            today = datetime.now(IST).date()
            result = snapshot_catalogs(client, args.catalog_db, today)
            result["amazon_pages"] = snapshot_asins(client, args.catalog_db, today)
            write_output(result, args.output)
            if result["errors"]:
                raise SystemExit(1)
            return
        if args.cmd == "crawl":
            crawl(client, store, args)
            return
        value = store.report(args.category) if args.cmd == "report" else spike(client, args.public)
        if value is None:
            parser.error("Unknown category")
        write_output(value, args.output)


def write_output(value, path):
    output = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    try:
        main()
    except (SourceUnavailable, ValueError) as exc:
        sys.exit(str(exc))
