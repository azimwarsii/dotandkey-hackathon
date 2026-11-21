"""Monthly relative-demand scenarios for a fixed cohort of observed products."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from statistics import mean

from .gaps import cohort, dated_reviews

MIN_MONTHS = 6
HORIZON = 3


def _month(d, step=0):
    year, month = divmod(d.year * 12 + d.month - 1 + step, 12)
    return date(year, month + 1, 1)


def _key(d):
    return d.isoformat()[:7]


def _rating_panel(snapshots, products, months, as_of):
    """Prorate measured changes, accepting intervals of 7–45 days without counter resets."""
    from .metrics import utc_date

    dates = defaultdict(dict)
    for item in snapshots:
        ref = item.get("product_ref")
        stamp = utc_date(item.get("captured_at"))
        count = item.get("rating_count")
        if ref not in products or not stamp or stamp > as_of or type(count) not in (float,int) or count < 0:
            continue
        if item.get("rating_scope") == "parent_product":
            continue
        if not item.get("external_id") or not item.get("market") or item.get("source") in ("search_snippet","marketplace_search_card"):
            continue
        key = (ref,item["market"],item["external_id"])
        current = dates[key].get(stamp)
        if current is None or str(item["captured_at"]) >= current[0]:
            dates[key][stamp] = str(item["captured_at"]), int(count)
    values = defaultdict(lambda:defaultdict(float))
    coverage = defaultdict(Counter)
    for listing, entries in dates.items():
        ordered = sorted((d,c) for d,(_,c) in entries.items())
        for (start,a),(end,b) in zip(ordered,ordered[1:]):
            days = (end-start).days
            if not 7 <= days <= 45 or b < a:
                continue
            for month in months:
                length = (min(end, _month(month,1))-max(start,month)).days
                if length > 0:
                    coverage[listing][month] += length
                    values[listing][month] += (b-a) * length / days
    brands = {p["brand"] for p in products.values()}
    for width in range(len(months), MIN_MONTHS - 1, -1):
        window = months[-width:]
        matched = [listing for listing, counts in coverage.items()
                   if all(counts[m] == (_month(m,1)-m).days for m in window)]
        if matched and {products[k[0]]["brand"] for k in matched} == brands:
            series = {m:sum(values[k][m] for k in matched) for m in window}
            details = {m:dict(sorted((ref,sum(values[k][m] for k in matched if k[0] == ref))
                              for ref in {k[0] for k in matched})) for m in window}
            return series, details, [{"product_ref":k[0],"market":k[1],"external_id":k[2]} for k in sorted(matched)]
    return {}, {}, []


def _fit(points, x_new):
    """OLS with an intercept. Time coordinates preserve gaps between observed months."""
    x_bar, y_bar = mean(x for x,_ in points), mean(y for _,y in points)
    denom = sum((x-x_bar)**2 for x,_ in points)
    slope = sum((x-x_bar)*(y-y_bar) for x,y in points)/denom
    return [max(0.0,y_bar+slope*(x-x_bar)) for x in x_new], slope


CHANNELS = ("flipkart", "amazon", "nykaa", "myntra", "purplle", "tira")


def _share(raw, rows, products, months, as_of):
    from .metrics import utc_date

    brands = {p["brand"] for p in products.values()}
    latest = {}
    identities = defaultdict(set)
    for snap in raw.get("listing_snapshots", []):
        if snap.get("external_id"):
            identities[snap.get("market"), snap["external_id"]].add(snap.get("product_ref"))
    for snap in raw.get("listing_snapshots", []):
        if snap.get("rating_scope") == "parent_product":
            continue
        ref, market, count = snap.get("product_ref"), snap.get("market"), snap.get("review_count")
        when = utc_date(snap.get("captured_at"))
        if ref not in products or market not in CHANNELS or not when or when > as_of or type(count) is not int or count < 0:
            continue
        external = snap.get("external_id")
        if not external or len(identities[market,external]) > 1 or snap.get("source") in ("search_snippet", "marketplace_search_card"):
            continue
        key = (ref, market)
        if key not in latest or str(snap["captured_at"]) > str(latest[key]["captured_at"]):
            latest[key] = snap
    complete = defaultdict(Counter)
    recent = defaultdict(Counter)
    for r in rows:
        ref, market = r["product_ref"],r.get("source")
        if market in CHANNELS:
            complete[market][ref] += 1
            day = utc_date(r.get("date"))
            if day and months[0] <= day < _month(as_of):
                recent[market][ref] += 1
    counters = defaultdict(dict)
    for (ref,market), snap in latest.items():
        counters[market][ref] = snap["review_count"]
    def valid(by_ref):
        return len(brands) == 6 and {products[ref]["brand"] for ref in by_ref} == brands and sum(by_ref.values()) > 0

    groups = ((counters, "listing_review_counts", "Cumulative explicitly reported review counts at the latest eligible PDP observation."),
              (recent, "dated_review_sample", f"Dated review texts from {_key(months[0])} through {_key(months[-1])}."),
              (complete, "full_review_sample", f"All review texts with known publication or observation by {as_of}."))
    for data,source,scope in groups:
        # Prefer maximum product coverage. Resolve ties using the fixed channel order.
        eligible = [m for m in CHANNELS if valid(data.get(m,{}))]
        if eligible:
            market = max(eligible, key=lambda m:len(data[m]))
            selected = dict(data[market])
            markets = dict.fromkeys(selected, market)
            break
    else:
        # No marketplace covers all six brands. Count one channel per SKU so that
        # collecting the same SKU twice cannot double its contribution to the share.
        shared = [m for m in CHANNELS if any(products[r]["brand"] == "Dot & Key" for r in complete[m])
                  and any(products[r]["brand"] != "Dot & Key" for r in complete[m])]
        selected, markets = {}, {}
        for ref in sorted(products):
            match = next((m for m in shared if ref in complete[m]), None)
            if match:
                selected[ref],markets[ref] = complete[match][ref],match
        source = "one_marketplace_per_product_sample"
        scope = (f"All eligible collected texts through {as_of}; one marketplace per product in fixed priority "
                 "Flipkart, Amazon, Nykaa, Myntra, Purplle, Tira. Marketplaces must cover the focal brand and peers. "
                 "Collection depths and the number of catalog products per brand differ.")
    by_brand = {b:sum(v for k,v in selected.items() if products[k]["brand"] == b) for b in sorted(brands)}
    denom = sum(by_brand.values())
    ok = valid(selected)
    return {"dk_share":by_brand.get("Dot & Key",0)/denom if ok else None, "dk_review_volume":by_brand.get("Dot & Key",0),
            "top_six_review_volume":denom, "review_volume_by_brand":by_brand, "share_source":source if ok else None,
            "share_scope":scope, "share_observations":[{"product_ref":r,"market":markets[r],"volume":selected[r],
                **({"url":latest[r,markets[r]].get("url"),"captured_at":latest[r,markets[r]]["captured_at"]}
                   if source=="listing_review_counts" else {})} for r in sorted(selected)],
            "brands_represented":len({products[r]["brand"] for r in selected})}


def build_forecast(raw_report, metrics, gaps, as_of):
    from .metrics import utc_date

    products = cohort(raw_report, as_of)
    rows = dated_reviews(raw_report, products, as_of)
    months = [_month(as_of, -i) for i in range(12,0,-1)]
    brand_for = {k:p["brand"] for k,p in products.items()}
    brands = sorted(set(brand_for.values()))
    own, peers = set(), set()
    for r in rows:
        if r.get("source") not in {"amazon","flipkart","nykaa","myntra","purplle","tira"}:
            continue
        when = utc_date(r.get("date"))
        if when and months[0] <= when < _month(as_of):
            (own if brand_for[r["product_ref"]].casefold() == "dot & key" else peers).add(r["source"])
    comparable = own & peers
    raw_counts = defaultdict(Counter)
    dated_by_brand = Counter()
    all_counts = defaultdict(Counter)
    for r in rows:
        when = utc_date(r.get("date"))
        if not when or not months[0] <= when < _month(as_of):
            continue
        ref = r["product_ref"]
        month = _month(when)
        all_counts[month][ref] += 1
        if r["source"] in comparable:
            raw_counts[month][ref] += 1
            dated_by_brand[brand_for[ref]] += 1
    sampled_series = {m:sum(raw_counts[m].values()) for m in months if raw_counts[m]}
    measured, increments, panel = _rating_panel(raw_report.get("listing_snapshots", []),products,months,as_of)
    source = "stable same-listing rating-count increments" if measured else "dated reviews from shared marketplaces"
    active = measured or sampled_series
    comparison = {k:dated_by_brand[k] for k in brands}
    share_data = _share(raw_report, rows, products, months, as_of)
    share = share_data["dk_share"]
    series = [{"month":_key(m),"all_source_dated_reviews":sum(all_counts[m].values()),
               "dated_reviews":sampled_series.get(m), "dated_reviews_by_product":dict(sorted(raw_counts[m].items())),
               "rating_increment":round(measured[m],3) if m in measured else None,
               "rating_increments_by_product":{k:round(v,3) for k,v in increments.get(m,{}).items()}}
              for m in months]
    # Whitespace cells overlap across axes. Count independent cell signatures once.
    concepts = {"cell:" + r["id"] for r in gaps.get("whitespace", [])}
    concepts.update("need:" + (r.get("aspect") or r["id"]) for r in gaps.get("category_pain", []))
    concepts.update("need:" + (r.get("theme") or r["id"]) for r in gaps.get("unmet_needs", []))
    gap_count = len(concepts)
    result = {"category":raw_report["category"],"status":"insufficient_history","source":source,"series":series,"projection":[],
              "forecast_growth":None,"opportunity_score":None,"n":round(sum(active.values()), 3), "as_of":as_of.isoformat(),
              "score_factors":{**share_data,"gap_count":gap_count,"gap_concepts":sorted(concepts),"dk_share":round(share,5) if share is not None else None,
                               "sampled_marketplace_reviews_by_brand":comparison, "review_window":[_key(months[0]),_key(months[-1])]},
              "evidence":{"rating_panel":panel,"shared_marketplaces":sorted(comparable),"matched_brands":brands},
              "method":{"horizon_months":HORIZON,"period":"last 12 complete calendar months",
                        "model":"fixed-parameter ordinary least squares on observed monthly counts, nonnegative projection",
                        "index":"100 = mean of the most recent three complete observed months",
                        "history_threshold":"≥6 observed months, all latest 3 observed, and ≥30 observations in the fit.",
                        "score_formula":"forecast_growth × (1 − D&K review-volume share) × distinct gap count",
                        "coverage":"Primary source is a stable rating-count panel covering every compared brand; otherwise use dated reviews on marketplaces shared by brand and peers. Sources are never added together.",
                        "sampling":"Marketplace pages surface a selected sample of reviews. The index estimates activity in that sample; it cannot estimate unit sales."}}
    recent = [active.get(m) for m in months[-3:]]
    if len(active) < MIN_MONTHS or any(v is None for v in recent) or sum(active.values()) < 30:
        result["reason"] = "Available month and volume coverage falls below the fit threshold."
        return result
    baseline = mean(recent)
    if baseline <= 0:
        result["reason"] = "The latest three complete months have zero mean activity."
        return result
    points = [(i,active[m]) for i,m in enumerate(months) if m in active]
    future, slope = _fit(points,range(12,12+HORIZON))
    growth = mean(future) / baseline - 1
    for entry, m in zip(series,months):
        entry["index"] = round(active[m]*100/baseline,2) if m in active else None
    result.update(status="sample_projection", forecast_growth=round(growth,5),
                  projection=[{"month":_key(_month(as_of,i)),"index":round(value*100/baseline,2)} for i,value in enumerate(future)],
                  slope_per_month=round(slope,3), fit_months=len(points), baseline=round(baseline,3))
    if share is not None:
        result["opportunity_score"] = round(growth*(1-share)*gap_count,5)
    else:
        result["reason"] = "The top-six review-volume comparison lacks coverage of at least one brand."
    return result
