"""Attribute supply, neighboring review demand, category pain, and explicit customer wishes."""
from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
from itertools import product as combinations
import json
import math
import re
from statistics import median

from .attributes import attributes, category_for
from .aspects import tag_sentence

WISH = re.compile(r"\b(?:wish(?:ed)?\s+(?:it|they|there|this)|if only|would be (?:great|perfect|better|nice) if|please\s+(?:launch|make|bring)|looking for (?:a|an)|should come in|needs?\s+(?:a|an|more))\s+([^.!?;\n]{3,220})", re.I)
STOP = set("a an and as be but by can could for from have i in is it more my of on one or that the them they this to was with would".split())
WISH_ATTRIBUTES = {
    "larger pack": r"bigger|larger|big(?:ger)? (?:bottle|size)|more quantity",
    "smaller pack": r"smaller|travel[- ]size|trial[- ]size|mini (?:size|pack)",
    "refill": r"\brefill", "fragrance-free": r"fragrance[- ]free|unscented|no (?:scent|fragrance)",
    "pump packaging": r"\bpump\b", "tinted": r"\btint(?:ed)?\b", "lower price": r"cheaper|affordable|lower price",
}


def _id(prefix, *parts):
    return prefix + "-" + sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:14]


def cohort(raw, as_of=None):
    """The focal brand's singles and the currently ranked competitor products only."""
    from .metrics import utc_date

    refs = {r["product_ref"] for r in raw.get("competitor_set", [])}
    selected = {}
    for p in raw.get("products", []):
        published = utc_date(p.get("published_at"))
        if p.get("is_combo") or (as_of and published and published > as_of):
            continue
        if p.get("brand", "").casefold() == "dot & key" or p["product_ref"] in refs:
            selected[p["product_ref"]] = p
    return selected


def dated_reviews(raw, refs, as_of):
    from .metrics import utc_date

    seen = set()
    rows = []
    for r in raw.get("reviews", []):
        if r.get("product_ref") not in refs:
            continue
        when = utc_date(r.get("date"))
        observed = utc_date(r.get("observed_at"))
        if (when and when > as_of) or (observed and observed > as_of) or not (when or observed):
            continue
        body = " ".join(str(r.get("body") or "").split()).casefold()
        key = r["product_ref"], body
        if body and key not in seen:
            rows.append(r)
            seen.add(key)
    return sorted(rows, key=lambda r: (str(r.get("product_ref")), str(r.get("date") or ""), str(r.get("source")), r["body"]))


def _themes(clause):
    from .trends import find_terms

    themes = [theme for theme, pattern in WISH_ATTRIBUTES.items() if re.search(pattern, clause, re.I)]
    themes += sorted(find_terms(clause))
    themes += sorted(tag_sentence(clause))
    return list(dict.fromkeys(themes))[:4]


def _tokens(clause):
    return {w for w in re.findall(r"[a-z0-9]+", clause.casefold()) if w not in STOP}


def _leftover_clusters(clauses):
    """Use only explicitly installed local weights; inference never downloads a model."""
    from .minilm import FILES, REVISION, embed, model_dir

    if len(clauses) < 2:
        return [[clause] for clause in clauses], "No unresolved clause pair to cluster."
    path = model_dir()
    if all((path / name).is_file() for name in FILES):
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            from threadpoolctl import threadpool_limits

            vecs = embed(clauses, path)
            with threadpool_limits(limits=1):
                labels = KMeans(n_clusters=min(5, int(math.sqrt(len(clauses)))), n_init=10,
                                random_state=42, algorithm="lloyd").fit_predict(vecs)
            groups = []
            for label in sorted(set(labels)):
                members = np.flatnonzero(labels == label)
                affinity = vecs[members] @ vecs[members].T
                # Name a group using an actual request. Low-affinity outliers must
                # not turn a single request into evidence for a recurring need.
                order = np.argsort(-affinity.mean(axis=1), kind="stable")
                compatible = []
                for idx in order:
                    if all(affinity[idx, other] >= 0.60 for other in compatible):
                        compatible.append(idx)
                    else:
                        groups.append([clauses[members[idx]]])
                groups.append([clauses[members[i]] for i in compatible])
            return groups, f"Local MiniLM {REVISION[:12]} (ONNX int8), KMeans seed 42, minimum within-group cosine 0.60."
        except (ImportError, OSError, ValueError, RuntimeError):
            pass
    groups = []
    for clause in clauses:
        tokens = _tokens(clause)
        for representative, group in groups:
            union = tokens | representative
            if union and len(tokens & representative) / len(union) >= 0.5:
                group.append(clause)
                break
        else:
            groups.append((tokens, [clause]))
    return [group for _, group in groups], "lexical token Jaccard ≥ 0.50, sorted representative order"


def _wish_matches(body):
    """Only open, reviewer-attributed requests count toward unmet demand."""
    for match in WISH.finditer(body):
        cue = match[0].casefold()
        if cue.startswith(("looking for", "need a", "need an", "needs a", "needs more", "need more")):
            prefix = re.split(r"[.!?;\n]", body[:match.start()])[-1].casefold()
            request = (re.search(r"(?:^|\b)(?:i(?: am|['’]m)?|we(?: are|['’]re)?|i am still|still|this product|this pack|it)\s*$", prefix)
                       or not prefix.strip())
            sentence = prefix + " " + cue
            if not request or re.search(r"\b(?:recommend|go for it|worked perfectly|excellent option|found one|finally found|this is perfect|pea[- ]sized|proper cleanse|good cleanse)\b", sentence):
                continue
            if re.search(r"\b(?:for anyone|if you|if u|you are|you['’]re|was|were)\b", prefix):
                continue
        yield match


def _unmet_needs(reviews, category):
    from .metrics import review_evidence

    themes = defaultdict(dict)
    unmatched = defaultdict(dict)
    for review in reviews:
        for match in _wish_matches(review["body"]):
            clause = " ".join(match[1].split()).strip(" ,").casefold()
            if not _tokens(clause):
                continue
            ev = review_evidence(review, match[0].strip())
            identity = ev["review_id"], review["product_ref"]
            labels = _themes(clause)
            for label in labels:
                themes[label][identity] = ev
            if not labels:
                unmatched[clause][identity] = ev
    groups, method = _leftover_clusters(sorted(unmatched))
    for group in groups:
        for clause in group:
            themes[group[0]].update(unmatched[clause])
    rows = []
    for label, matches in themes.items():
        if len(matches) < 2:
            continue
        evidence = list(matches.values())
        rows.append({"id": _id("need", category, label), "title": f"Customer requests mention {label.replace('_', ' ')}",
                     "theme": label, "n": len(matches), "evidence": evidence[:3],
                     "metric_values": {"distinct_reviews": len(matches), "products": len({x["product_ref"] for x in evidence})},
                     "threshold": "At least two distinct reviews must contain an explicit wish clause."})
    rows.sort(key=lambda r: (-r["n"], r["theme"]))
    return rows, method


def _pain(metrics, brands, category):
    all_brands = metrics.get("brands", {})
    by_key = {name.casefold(): value for name, value in all_brands.items()}
    own = by_key.get("dot & key", {}).get("aspects", {})
    rows = []
    for aspect, summary in own.items():
        if not summary.get("claim_eligible") or (summary.get("nss") or 0) >= 0:
            continue
        supported = {"Dot & Key": summary}
        for brand in sorted(brands - {"Dot & Key"}):
            item = by_key.get(brand.casefold(), {}).get("aspects", {}).get(aspect, {})
            if item.get("claim_eligible") and (item.get("nss") or 0) < 0:
                supported[brand] = item
        if len(supported) < 5:
            continue
        evidence = []
        for item in supported.values():
            quote = next((q for q in item.get("evidence", []) if q.get("polarity") == "negative" or q.get("polarity") == "neg"), None)
            if quote:
                evidence.append(quote)
        rows.append({"id":_id("pain",category,aspect), "title":f"{aspect.replace('_',' ')} draws complaints across {len(supported)} brands",
                     "aspect":aspect, "n":sum(s["directional_n"] for s in supported.values()), "evidence":evidence[:3],
                     "metric_values":{"negative_brands":{name:{"nss":s["nss"], "n":s["directional_n"]} for name,s in supported.items()}},
                     "threshold":"Negative NSS for Dot & Key and at least four ranked competitors, with validated tagging and ≥30 directional mentions per brand."})
    return sorted(rows, key=lambda r:(-r["n"],r["aspect"]))


def _cell_values(attrs, axes):
    vals = []
    for axis in axes:
        item = attrs.get(axis)
        if not item:
            return []
        vals.append(item if isinstance(item, list) else [item])
    return list(combinations(*vals))


def _supply(primary, context, category, as_of):
    from .metrics import utc_date

    covered = {p["brand"].casefold() for p in primary.values()}
    catalog = {}
    for p in context.get("products", []):
        if p.get("brand", "").casefold() not in covered or category_for(p) != category or p.get("is_combo"):
            continue
        created = utc_date(p.get("created_at"))
        if created and created > as_of:
            continue
        catalog[p["product_ref"]] = p
    # Count each entity once. For a brand with a category catalog, use that catalog
    # for supply and use its independently observed marketplace reviews for demand.
    with_catalog = {p["brand"].casefold() for p in catalog.values()}
    catalog.update({key:p for key,p in primary.items() if p["brand"].casefold() not in with_catalog})
    return catalog, sorted(with_catalog)


def _requested_cells(own_attrs, reviews, axes):
    """Fill unspecified attributes from the reviewed product only when a wish names an axis."""
    from .metrics import review_evidence

    requested = defaultdict(dict)
    for r in reviews:
        for match in _wish_matches(r["body"]):
            clause = match[1]
            if re.search(r"\b(?:no|not|without|wasn't|weren't)\b", clause, re.I):
                continue
            changes = attributes({"title":clause})
            cost = re.search(r"\b(?:under|below|less than)\s*(?:₹|rs\.?|inr)?\s*500\b", clause, re.I)
            if cost:
                changes["price_band"] = "under ₹500"
            explicit = {a:changes[a] for a in axes if changes.get(a)}
            if not explicit:
                continue
            fields = {**own_attrs[r["product_ref"]], **explicit}
            ev = review_evidence(r, match[0])
            for cell in _cell_values(fields, axes):
                requested[cell][(r["product_ref"], ev["review_id"])] = ev
    return requested


def _whitespace(primary, context, reviews, category, as_of):
    from .metrics import review_evidence

    suppliers, catalog_brands = _supply(primary, context, category, as_of)
    supply_attrs = {k:attributes(p) for k,p in suppliers.items()}
    own_attrs = {k:attributes(p) for k,p in primary.items()}
    sampled = defaultdict(list)
    for r in reviews:
        sampled[r["product_ref"]].append(r)
    threshold = max(30, math.ceil(median([len(v) for v in sampled.values()] or [0])))
    pairs = [("formats","price_band"), ("skin_types","price_band"), ("formats","skin_types")]
    if category.casefold() == "sunscreen":
        pairs.append(("formats","spf","price_band"))
    if category.casefold() == "serum":
        pairs.append(("ingredients","price_band"))
    rows, occupied = [], []
    for axes in pairs:
        matrix = defaultdict(set)
        for ref, fields in supply_attrs.items():
            for cell in _cell_values(fields, axes):
                matrix[cell].add(ref)
        demand = defaultdict(set)
        for ref, fields in own_attrs.items():
            for cell in _cell_values(fields, axes):
                if sampled.get(ref):
                    demand[cell].add(ref)
        for cell, refs in sorted(matrix.items()):
            volume = sum(len(sampled[r]) for r in demand[cell])
            occupied.append({"attributes":dict(zip(axes,cell)), "products":len(refs), "sampled_reviews":volume})
        if not matrix:
            continue
        requested = _requested_cells(own_attrs, reviews, axes)
        domains = [sorted({key[i] for key in matrix}) for i in range(len(axes))]
        for cell in sorted(set(combinations(*domains)) | set(requested)):
            suppliers_in_cell = matrix.get(cell, set())
            if len(suppliers_in_cell) > 1:
                continue
            directions = set()
            neighbors = set()
            for observed, refs in demand.items():
                refs = refs - demand.get(cell, set())
                if not refs:
                    continue
                diffs = [i for i, (a,b) in enumerate(zip(cell,observed)) if a != b]
                if len(diffs) == 1:
                    directions.add(diffs[0])
                    neighbors.update(refs)
            # Multi-valued products can occupy the target and an adjacent cell.
            # Count only neighboring demand for the distinct products outside the target.
            neighbors.difference_update(demand.get(cell, set()))
            n = sum(len(sampled[r]) for r in neighbors)
            neighboring_brands = {primary[r]["brand"] for r in neighbors}
            directly_requested = list(requested.get(cell, {}).values())
            nearby_support = n >= threshold and len(neighbors) >= 2 and len(directions) >= 2 and len(neighboring_brands) >= 2
            if not nearby_support and len(directly_requested) < 2:
                continue
            attr = dict(zip(axes,cell))
            labels = [f"SPF {value}" if axis == "spf" else str(value) for axis,value in attr.items()]
            evidence = directly_requested[:3]
            for ref in sorted(neighbors, key=lambda key:(-len(sampled[key]),key))[:3-len(evidence)]:
                evidence.append(review_evidence(sampled[ref][0]))
            unknown = sum(1 for fields in supply_attrs.values() if any(not fields.get(key) for key in axes)
                          and all(not fields.get(key) or val in (fields[key] if isinstance(fields[key],list) else [fields[key]])
                                  for key,val in attr.items()))
            rows.append({"id":_id("space",category,attr), "title":f"{' · '.join(labels)} has {len(suppliers_in_cell)} observed {'product' if len(suppliers_in_cell) == 1 else 'products'}",
                         "category":category,"attributes":attr,"n":n if nearby_support else len(directly_requested),"evidence":evidence,
                         "metric_values":{"suppliers":len(suppliers_in_cell),"supplier_refs":sorted(suppliers_in_cell),
                             "possible_suppliers_with_unknown_attributes":unknown, "neighbor_reviews":n,
                             "neighbor_products":sorted(neighbors), "neighbor_brands":sorted(neighboring_brands),
                             "matching_wishes":len(directly_requested)},
                         "threshold":f"≤1 observed supplier and ≥{threshold} adjacent sampled reviews from ≥2 products and brands on ≥2 adjacent axes, or ≥2 explicit customer requests for this cell."})
    # A format-price gap and that same gap at a specific SPF are nested hypotheses.
    # Keep the actual tested cells for inspection; count the common concept once.
    by_concept = defaultdict(list)
    attrs_present = {tuple(sorted(row["attributes"].items())) for row in rows}
    for row in rows:
        attrs = row["attributes"]
        base = {k:v for k,v in attrs.items() if k != "spf"}
        key = tuple(sorted(base.items()))
        by_concept[key if key in attrs_present else tuple(sorted(attrs.items()))].append(row)
    compact = []
    for group in by_concept.values():
        chosen = min(group, key=lambda r:(r["metric_values"]["possible_suppliers_with_unknown_attributes"],
                                         r["metric_values"]["suppliers"], -r["n"], -len(r["attributes"]), r["id"]))
        chosen["related_cells"] = [r["attributes"] for r in group if r is not chosen]
        compact.append(chosen)
    rows = compact
    rows.sort(key=lambda row:(row["metric_values"]["possible_suppliers_with_unknown_attributes"],
                              row["metric_values"]["suppliers"],-row["n"],row["id"]))
    return rows, occupied, {"supply_products":len(suppliers),"catalog_brands":catalog_brands,
        "demand_products":len(sampled),"neighbor_review_threshold":threshold,
        "scope":"Marketplace cohort and available same-category catalogs for ranked brands. Adjacent review volume is a demand proxy. Missing attributes leave possible additional suppliers."}


def build_gaps(raw_report, metrics, catalog_context, as_of):
    primary = cohort(raw_report, as_of)
    reviews = dated_reviews(raw_report, primary, as_of)
    category = raw_report["category"]
    needs, method = _unmet_needs(reviews, category)
    pain = _pain(metrics, {p["brand"] for p in primary.values()}, category)
    whitespace, matrix, scope = _whitespace(primary, catalog_context or {}, reviews, category, as_of)
    return {"category":category,"whitespace":whitespace,"category_pain":pain,"unmet_needs":needs,
            "attribute_matrix":matrix,"scope":scope,"clustering_method":method}
