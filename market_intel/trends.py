"""Term growth from dated Shopify creations and attributable, dated reviews."""
from __future__ import annotations

from calendar import monthrange
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from .competitors import _published

LEXICON = json.loads(Path(__file__).with_name("lexicons").joinpath("terms.json").read_text())
INGREDIENTS = tuple(LEXICON["ingredients"])
TERMS = {**LEXICON["ingredients"], **LEXICON["claims"]}
ALPHA = 0.005
MIN_SUPPORT = 15
MIN_GROWTH = 1.5


def normalize(text):
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", value))


ALIASES = {normalize(alias): term for term, aliases in TERMS.items() for alias in [term, *aliases]}
# Lookahead preserves overlapping terms, e.g. both copper peptide and peptide.
PATTERN = re.compile(r"(?=\b(" + "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True)) + r")\b)")


@lru_cache(maxsize=12000)
def find_terms(text):
    return frozenset(ALIASES[m[1]] for m in PATTERN.finditer(normalize(text)))


def product_text(p):
    tags = p.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    # Cross-sell, sale and collection tags can name other products' ingredients.
    tags = [tag for tag in tags if str(tag).casefold().startswith(("fltr_ingredients_", "fltr_skin_concern_", "st_ingredients_"))
            or normalize(tag) in ALIASES]
    fields = [p.get("title"), p.get("product_type"), p.get("description"), *tags,
              *p.get("ingredients", []), *p.get("concerns", [])]
    return " ".join(str(field) for field in fields if field)


def months_before(day, months):
    ordinal = day.year * 12 + day.month - 1 - months
    year, month = divmod(ordinal, 12)
    return date(year, month + 1, min(day.day, monthrange(year, month + 1)[1]))


@lru_cache(maxsize=None)
def _quote_pattern(term):
    aliases = [term, *TERMS[term]]
    expr = "|".join(r"[\W_]+".join(map(re.escape, normalize(alias).split())) for alias in aliases)
    return re.compile(r"\b(?:" + expr + r")\b", re.I)


def _excerpt(text, term):
    match = _quote_pattern(term).search(text)
    if not match:
        return text[:250]
    start = max(0, match.start() - 70)
    return text[start:max(start + 230, match.end())].strip()


def _signal(docs, base_start, boundary, end):
    totals = Counter()
    counts = defaultdict(Counter)
    examples = defaultdict(lambda: defaultdict(list))
    for when, text, evidence in docs:
        if not when or when < base_start or when >= end:
            continue
        period = "recent" if when >= boundary else "base"
        totals[period] += 1
        for term in find_terms(text):
            counts[term][period] += 1
            if len(examples[term][period]) < 3:
                sample = dict(evidence)
                source_text = sample.pop("review_text", None)
                if source_text is not None:
                    sample["quote"] = _excerpt(source_text, term)
                else:
                    sample["matched_text"] = _excerpt(text, term)
                examples[term][period].append(sample)
    results = {}
    for term in TERMS:
        base, recent = counts[term]["base"], counts[term]["recent"]
        recent_rate = recent / totals["recent"] if totals["recent"] else None
        base_rate = base / totals["base"] if totals["base"] else None
        growth = ((recent_rate + ALPHA) / (base_rate + ALPHA)
                  if recent_rate is not None and base_rate is not None else None)
        supported = (growth is not None and min(totals["base"], totals["recent"]) >= MIN_SUPPORT
                     and recent + base >= MIN_SUPPORT)
        results[term] = {"base_mentions": base, "recent_mentions": recent, "base_n": totals["base"],
                         "recent_n": totals["recent"], "base_rate": base_rate, "recent_rate": recent_rate,
                         "growth": growth, "supported": supported,
                         "rising": bool(supported and growth >= MIN_GROWTH),
                         "base_examples": examples[term]["base"], "recent_examples": examples[term]["recent"]}
    windows = {"base_start": str(base_start), "recent_start": str(boundary), "end_exclusive": str(end),
               "base_n": totals["base"], "recent_n": totals["recent"]}
    return results, windows


def build_trends(raw_report, catalog_context, as_of):
    from .catalog_history import corroborate_launches
    from .metrics import utc_date
    end = as_of + timedelta(days=1)
    recent_begin = months_before(end, 6)
    base_begin = months_before(recent_begin, 12)
    products = catalog_context.get("historical_products", catalog_context.get("products", []))
    # One creation per product ID in the category, including products that have since disappeared.
    product_docs = [(_published(p.get("created_at")), product_text(p), {
        "product_ref": p["product_ref"], "title": p["title"], "url": p["url"], "date": p.get("created_at")})
        for p in products]
    reviews = raw_report.get("reviews", [])
    review_docs = [(utc_date(r.get("date")), str(r.get("title") or "") + " " + str(r.get("body") or ""), {
        "product_ref": r.get("product_ref"), "source": r.get("source"), "date": r.get("date"),
        "url": r.get("source_url") or r.get("url"), "review_text": str(r.get("title") or "") + " " + str(r.get("body") or "")}) for r in reviews]
    launches, launch_window = _signal(product_docs, base_begin, recent_begin, end)
    mentions, review_window = _signal(review_docs, end - timedelta(days=360), end - timedelta(days=90), end)
    own = [p for p in raw_report.get("products", []) if normalize(p.get("brand")) in {"dot key", "dot and key"}
           and not p.get("is_combo")]
    existing = {t for p in own for t in find_terms(product_text(p))}
    measured = []
    for term in TERMS:
        a, b = launches[term], mentions[term]
        if not (a["base_mentions"] + a["recent_mentions"] + b["base_mentions"] + b["recent_mentions"]):
            continue
        qualified_growths = [signal["growth"] for signal in (a, b) if signal["rising"]]
        row = {"id": "trend:" + normalize(raw_report.get("category", "")).replace(" ", "-") + ":" + term.replace(" ", "-"),
               "n": a["base_mentions"] + a["recent_mentions"] + b["base_mentions"] + b["recent_mentions"],
               "growth": min(qualified_growths) if len(qualified_growths) == 2 else None,
               "term": term, "missing_at_dot_key": (term not in existing) if own else None,
               "dot_key_product_n": len(own), "signals": {"catalog_creations": a, "review_mentions": b},
               "rising_signal_count": int(a["rising"]) + int(b["rising"]),
               "sample_sizes": {"catalog": a["recent_n"] + a["base_n"], "reviews": b["recent_n"] + b["base_n"]},
               "evidence": a["recent_examples"] + b["recent_examples"]}
        measured.append(row)
    measured.sort(key=lambda r: (-r["rising_signal_count"], r["term"]))
    return {"trending": [r for r in measured if r["rising_signal_count"] >= 2], "terms": measured,
            "windows": {"catalog_creations": launch_window, "review_mentions": review_window},
            "thresholds": {"alpha": ALPHA, "growth": MIN_GROWTH, "min_term_mentions_per_signal": MIN_SUPPORT,
                           "min_documents_each_window": MIN_SUPPORT, "required_signals": 2},
            "scope": "Category products in tracked competitor catalogs and dated category reviews from Part 1.",
            "news_counts_available": False, "dictionary_size": len(TERMS),
            "coverage": catalog_context.get("coverage", []), "launches": corroborate_launches(raw_report, catalog_context),
            "price_changes": catalog_context.get("price_changes", [])}
