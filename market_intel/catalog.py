"""Collect the public Shopify catalog, retaining variants and bundle relationships."""

from __future__ import annotations

from collections import defaultdict
import json
import re

from selectolax.lexbor import LexborHTMLParser

from .client import SourceUnavailable

SHOP_URL = "https://www.dotandkey.com"
CATALOG_URL = SHOP_URL + "/products.json"

CATEGORIES = {
    "moisturiser": "Moisturiser", "moisturizer": "Moisturiser",
    "sunscreen": "Sunscreen", "face wash": "Face Wash", "serum": "Serum",
    "lip balm": "Lip Balm", "toner": "Toner", "mask": "Mask",
    "eye care": "Eye", "bodycare": "Body", "haircare": "Hair", "combo": "Combo",
}
SIZE = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(ml|gm?|kg|l|oz|pairs?)\b", re.I)
# Catalog titles often carry the hero ingredient even when the filter tags are missing.
TITLE_INGREDIENT = re.compile(
    r"\b(vitamin [ce](?:\s*\+\s*[ce])?|plant pdrn|dragon fruit|rice water|argan oil|"
    r"hyaluronic(?: acid)?|ceramides?|peptides?|niacinamide|cica|probiotics?|retinol|"
    r"salicylic(?: acid)?|glycolic(?: acid)?|strawberry|watermelon|pomegranate|"
    r"blueberry|mango|moringa|green tea)\b", re.I)
SPF = re.compile(r"\bSPF\s*[-:]?\s*(\d+(?:\.\d+)?\+?)", re.I)

# The Shopify feed lists flavours or shades for these products. Their PDP's
# “More Information” section declares a single Net Qty. Scope each observation
# to the checked SKUs so future sizes or multipacks cannot inherit it.
PDP_NET_QTY = {
    "hydrating-lip-balm": ("4.5g", {"DK_LBSR", "DK_LBCCR", "DK_LBCN", "DK_LBBB"}),
    "spf-50-barrier-repair-lip-balm": ("10g", {"DK_BRWN", "DK_BRPP", "DK_BRRR"}),
    "lip-plumping-sleeping-mask": ("15ml", {"DK_MNLSMH"}),
    "meltie-lipbalm": ("4g", {"DK_MLBCC", "DK_MLBBC", "DK_MLBSG"}),
    "plushie-jelly-lip-balm": ("10g", {"DK_LBPJ", "DK_LBBK", "DK_LBBG"}),
    "spf-30-vitamin-c-e-lip-balm": ("12g", {"DK_LBSC", "DK_LBCP", "DK_LBWMC", "DK_LBCM", "DK_LBWMR"}),
    "strobe-creams-highlighter-moisturizer": ("30ml", {"DK_SDSC"}),
    "strawberry-dew-tinted-sunscreen-spf-50-pa": ("50ml", {
        "DK_SDTS00", "DK_SDTS01", "DK_SDTS01A", "DK_SDTS02", "DK_SDTS02A", "DK_SDTS03",
        "DK_SDTS03A", "DK_SDTS04", "DK_SDTS05", "DK_SDTS06", "DK_SDTS07", "DK_SDTS08",
        "DK_SDTS08A", "DK_SDTS09", "DK_SDTS010",
    }),
}

# Opaque bundle codes cannot be split into the constituent Shopify variant SKUs.
# These product-level mappings were verified against the Product Details and
# Net Qty sections of the Dot & Key PDP at /products/<bundle handle>.
BUNDLE_CODES = {
    "high-on-hydration-combo": ["BRHFW", "HGPR"],
    "break-up-with-acne-combo-2": ["NVCCBC", "CNGS", "CRNG", "CCNS"],
    "instant-dewy-skin-combo": ["SDSC", "SDSS"],
    "moisturize-protect-duo": ["CHBFC", "VCES"],
    "glow-protect-vitamin-c-duo": ["FNVVCEM", "VCES"],
    "vitamin-c-daily-essential-combo": ["FNVVCEM", "VCEFS"],
    "hydration-must-have-duo-1": ["BRHFW", "CHBFC"],
    "all-day-hydration-trio-1": ["NVDPMFC", "RPHT", "HGPR"],
    "best-of-vitamin-c-skincare-trio": ["VCFW", "VCEFS", "FNVVCEM"],
    "cica-superstar-trio": ["NVCCBC", "CSCT", "CRNG"],
    # Each lip duo contains two variants of a single balm line.
    "spf-50-vitamin-c-e-lip-balm-pack-of-2": ["LBSC"],
    "spf-50-barrier-repair-hydrating-lip-balm-pack-of-2": ["LBSR"],
}


def clean_text(value):
    if not value:
        return ""
    tree = LexborHTMLParser(str(value))
    for node in tree.css("script, style, template, noscript"):
        node.decompose()
    return " ".join(tree.text(separator=" ", strip=True).split())


def size_in(text):
    match = SIZE.search(text or "")
    if match:
        number, unit = match.groups()
        unit = {"gm": "g", "pair": "pairs"}.get(unit.lower(), unit.lower())
        return f"{number} {unit}"
    return None


def _tag_values(tags, prefix):
    return list(dict.fromkeys(tag[len(prefix):].strip() for tag in tags
                              if tag.lower().startswith(prefix)
                              and tag[len(prefix):].strip().casefold() not in {"", "other", "others"}))


def _money(value):
    return float(value) if value not in ("", None) else None


def _normalize(raw):
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [tag.strip() for tag in tags.split(",")]
    ptype = raw.get("product_type", "").strip()
    title = raw["title"]
    variants = [{
        "id": v["id"], "sku": v.get("sku"), "title": v.get("title"),
        "size": size_in(v.get("title")), "price": _money(v.get("price")),
        "mrp": _money(v.get("compare_at_price")), "available": v.get("available"),
    } for v in raw.get("variants", [])]
    quantity = PDP_NET_QTY.get(raw["handle"])
    url = f"{SHOP_URL}/products/{raw['handle']}"
    if quantity and raw.get("options") and all(o.get("name", "").casefold() in {"color", "colour", "shade", "flavour", "flavor"}
                        for o in raw.get("options", [])):
        label, observed_skus = quantity
        for v in variants:
            if v["sku"] in observed_skus and not v["size"]:
                v["size"] = size_in(label)
                v["size_source"] = {"url": url, "field": "Net Qty", "value": label, "checked_on": "2026-11-21"}
                if v["sku"] == "DK_MLBBC":
                    v["size_source"]["url"] = url + "?variant=46066400657573"
                    v["size_source"]["corroboration"] = (
                        SHOP_URL + "/blogs/skin-care/success-story-of-dot-and-key-meltie-lip-balm"
                    )
                if v["sku"] == "DK_MLBCC":
                    # The balm PDP's regulatory text names Strawberry Glaze.
                    # The Cocoa Sun-kissed Duo explicitly declares this balm at 4 g.
                    v["size_source"].update(url=SHOP_URL + "/products/strawberry-cocoa-sun-kissed-duo",
                                            value="1N - Meltie Lip Balm 4g")
    first = next((v for v in variants if v["available"]), variants[0] if variants else {})
    description = clean_text(raw.get("body_html"))
    tags_lower = {t.casefold() for t in tags}
    ingredients = _tag_values(tags, "fltr_ingredients_")
    skin_type = _tag_values(tags, "fltr_skin_type_")
    if not skin_type:
        skin_type = [t[:-5] for t in tags if t.casefold() in
                     {"dry skin", "sensitive skin", "oily skin", "normal skin", "combination skin"}]
    spf = SPF.search(title) or SPF.search(description)
    title_ingredients = list(dict.fromkeys(m.group() for m in TITLE_INGREDIENT.finditer(title)))
    return {
        "product_ref": f"dk:{raw['id']}", "id": raw["id"], "handle": raw["handle"],
        "url": url, "title": title,
        "brand": "Dot & Key", "category": CATEGORIES.get(ptype.casefold(), ptype or "Uncategorized"),
        "product_type": ptype, "description": description, "tags": tags, "variants": variants,
        "concerns": _tag_values(tags, "fltr_skin_concern_"), "ingredients": ingredients or title_ingredients,
        "hero_ingredient": (title_ingredients or [None])[0],
        "skin_type": skin_type, "spf": spf.group(1) if spf else None,
        "size": first.get("size") or size_in(title), "price": first.get("price"), "mrp": first.get("mrp"),
        **({"size_source": first["size_source"]} if "size_source" in first else {}),
        "currency": "INR", "images": [img["src"] for img in raw.get("images", []) if img.get("src")],
        "published_at": raw.get("published_at"), "is_combo": ptype.casefold() == "combo",
        "is_new": bool(tags_lower & {"_newarrivals", "new arrivals", "just in", "_newlaunch"})
                  or any(t.startswith("fltr_dnk_new_arrival_") for t in tags_lower),
        "component_refs": [],
    }


def _fill_gaps(client, product):
    fields = {
        "hero_ingredient": {"type": "string", "description": "Explicitly named hero ingredient"},
        "skin_type": {"type": "array", "items": {"type": "string"}},
        "size": {"type": "string", "description": "Single-unit net quantity, including its unit"},
    }
    if product["category"] == "Hair":
        del fields["skin_type"]
    else:
        fields["skin_type"]["items"]["enum"] = ["Oily", "Dry", "Combination", "Sensitive", "Normal", "Acne-prone", "All skin types"]
    if product["category"] in {"Sunscreen", "Lip Balm", "Moisturiser"}:
        fields["spf"] = {"type": "string", "description": "Advertised numeric SPF, retaining +"}
    missing = {key: schema for key, schema in fields.items() if not product[key]}
    if not missing:
        return
    source = "\n".join([product["title"], product["description"], ", ".join(product["tags"]),
                        ", ".join(v["title"] or "" for v in product["variants"])])
    values = client.extract({"type": "object", "properties": missing, "additionalProperties": False}, source)
    for key in missing:
        value = values.get(key)
        candidates = value if key == "skin_type" and isinstance(value, list) else [value]
        supported, quotes = [], []
        for candidate in candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            candidate = candidate.strip()
            if key == "skin_type" and candidate not in fields["skin_type"]["items"]["enum"]:
                continue
            pattern = re.escape(candidate)
            if key == "spf":
                if not re.fullmatch(r"\d+\+?", candidate):
                    continue
                pattern = r"\bSPF[\s:_-]*" + pattern + r"(?![\d+])"
            if key == "size":
                candidate = size_in(candidate)
                if not candidate:
                    continue
                pattern = re.escape(candidate).replace(r"\ ", r"\s*")
            found = re.search(pattern, source, re.I)
            if found:
                supported.append(candidate)
                quotes.append(source[max(found.start()-45, 0):found.end()+45].strip())
        if supported:
            product[key] = supported if key == "skin_type" else supported[0]
            product.setdefault("extraction_evidence", {})[key] = {
                "url": product["url"], "excerpts": quotes,
                "method": "source-matched model extraction",
                "model": getattr(client, "extraction_model", None),
            }


def _link_components(products):
    index = defaultdict(set)
    original_skus = defaultdict(set)
    for p in products:
        if not p["is_combo"]:
            for variant in p["variants"]:
                sku = (variant["sku"] or "").upper().removeprefix("DK_")
                if sku:
                    index[sku].add(p["product_ref"])
                    original_skus[sku].add(variant["sku"])
    for combo in (p for p in products if p["is_combo"]):
        codes = BUNDLE_CODES.get(combo["handle"])
        origin = "product_page" if codes else "variant_sku"
        if codes is None:
            codes = []
            for v in combo["variants"]:
                codes += re.split(r"DK_|[_+]", (v["sku"] or "").upper())
        refs = []
        matched_skus = []
        for code in codes:
            # Some composite SKUs append a pack quantity or revision digit.
            lookup = code if code in index else re.sub(r"[12]$", "", code)
            if len(index.get(lookup, ())) == 1:
                refs.extend(index[lookup])
                if origin == "variant_sku":
                    matched_skus.extend(sorted(original_skus[lookup]))
        combo["component_refs"] = list(dict.fromkeys(refs))
        combo["component_skus"] = list(dict.fromkeys(matched_skus))
        combo["component_source"] = origin if refs else None


def collect_catalog(client):
    raw_by_id = {}
    page = 1
    while True:
        try:
            payload = json.loads(client.get(CATALOG_URL, {"limit": 250, "page": page}))
        except ValueError as exc:
            raise SourceUnavailable(f"Shopify returned invalid JSON on page {page}") from exc
        raw = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(raw, list) or not all(
                isinstance(item, dict) and all(item.get(k) for k in ("id", "handle", "title"))
                for item in raw):
            raise SourceUnavailable(f"Invalid Shopify catalog page {page}")
        if not raw:
            break
        new_records = {p["id"]: p for p in raw if p["id"] not in raw_by_id}
        if not new_records:
            raise SourceUnavailable(f"Shopify repeated catalog page {page}")
        raw_by_id.update(new_records)
        page += 1
    products = [_normalize(raw) for raw in raw_by_id.values()
                if raw.get("product_type", "").strip().casefold() != "free"]
    _link_components(products)
    for product in products:
        if not product["is_combo"]:
            _fill_gaps(client, product)
    return products
