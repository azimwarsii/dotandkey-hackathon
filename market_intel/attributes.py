"""Category and attribute extraction shared by catalog history and insight rules."""
from __future__ import annotations

import re
from html import unescape

CATEGORY_RULES = (
    ("Lip Balm", r"\blip\s*(?:balm|mask|butter|treatment|gloss|oil|care)\b"),
    ("Eye", r"\b(?:under[ -]?eye|eye\s*(?:cream|patch|serum|gel|mask))"),
    ("Hair", r"\b(?:hair|shampoo|conditioner|scalp)\b"),
    ("Sunscreen", r"\b(?:sunscreens?|sun\s*screen|sunblock|sun\s*stick|sun protection lotion)\b"),
    ("Body", r"\b(?:body|underarms?|roll[ -]?on|shower|deodorant|hand cream|foot cream)\b"),
    ("Face Wash", r"\b(?:face\s*wash|facial wash|cleanser|cleansing (?:foam|gel|balm|oil|milk))\b"),
    ("Toner", r"\b(?:toners?|toning water|essence water)\b"),
    ("Mask", r"\b(?:face pack|face masks?|clay mask|sheet mask|peel[ -]?off mask|sleeping mask|mud mask)\b"),
    ("Serum", r"\b(?:face\s*)?serums?\b"),
    ("Moisturiser", r"\b(?:moisturi[sz](?:ers?|ing)|face cream|day cream|night (?:cream|gel)|facial cream|barrier cream)\b"),
)
CATEGORY_NAMES = {label.casefold(): label for label, _ in CATEGORY_RULES}
CATEGORY_NAMES.update({"moisturizer":"Moisturiser", "moisturizers":"Moisturiser", "body care":"Body",
                       "eye care":"Eye", "hair care":"Hair", "facewash":"Face Wash", "face mask":"Mask"})
FORMATS = ("gel", "cream", "stick", "spray", "mist", "tinted", "serum", "lotion", "foam", "balm", "oil",
           "toner", "mask", "patch", "fluid", "powder", "roll-on", "milk", "sorbet", "shampoo", "conditioner")
SKIN = ("oily", "dry", "combination", "normal", "sensitive", "acne-prone")


def category_for(product):
    stored = CATEGORY_NAMES.get(str(product.get("category") or "").casefold().strip())
    if stored:
        return stored
    title = str(product.get("title") or "")
    if re.search(r"\b(?:lipstick|mascara|eyeliner|eyeshadow|kajal|foundation makeup|concealer)\b", title, re.I):
        return None
    if re.search(r"\bbody\s+lotion\b", title, re.I):
        return "Body"
    if re.search(r"serum[- ]lotion", title, re.I):
        context = " ".join(_values(product.get(key)) for key in ("product_type", "tags", "description"))
        if re.search(r"\bbody\b", context.replace("_", " "), re.I):
            return "Body"
    kind = CATEGORY_NAMES.get(str(product.get("product_type") or "").casefold().strip())
    if kind:
        return kind
    for text in (product.get("title"), product.get("product_type")):
        for label, pattern in CATEGORY_RULES:
            if re.search(pattern, str(text or ""), re.I):
                return label
    return None


def _values(value):
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    return str(value or "")


def attributes(product):
    """Return only observed claims and pack data. Price is the listed pack price in INR."""
    from .trends import INGREDIENTS, find_terms

    title = str(product.get("title") or "")
    description = unescape(re.sub("<[^>]+>", " ", str(product.get("description") or product.get("body_html") or "")))
    tags = product.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    # Filter storefront merchandising tags: cross-sell rules frequently name other actives.
    claims = " ".join(str(t).replace("_", " ") for t in tags if str(t).lower().startswith(("fltr_skin_type", "fltr_ingredients", "st_ingredients")))
    skin_text = (_values(product.get("skin_type")) + " " + title + " " + claims).lower()
    spf = re.search(r"\bspf[\s:-]*(\d{1,3})", title + " " + description, re.I)
    direct_spf = re.search(r"\d{1,3}", str(product.get("spf") or ""))
    pa = re.search(r"\bpa\s*(\+{1,4})", title + " " + description, re.I)
    title_terms = set(find_terms(title + " " + _values(product.get("ingredients")) + " " + claims + " " + _values(product.get("hero_ingredient"))))
    if not title_terms:
        title_terms = set(find_terms(description[:350]))
    formats = []
    for name in FORMATS:
        pattern = {"foam":r"\bfoam(?:ing)?\b", "roll-on":r"\broll[- ]?on\b",
                   "oil":r"\b(?:cleansing oil|face oil|hair oil|lip oil|facial oil|body oil)\b",
                   "patch":r"\bpatch(?:es)?\b"}.get(name, r"\b" + name + r"s?\b")
        if re.search(pattern, title, re.I):
            formats.append(name)
    skin_types = [kind for kind in SKIN if re.search(r"\b" + kind.replace("-", "[- ]") + r"\b", skin_text)]
    if not skin_types and re.search(r"all skin types", skin_text):
        skin_types = ["all skin types"]
    try:
        price = float(product["price"])
        if price <= 0 or str(product.get("currency", "INR")).upper() != "INR":
            price = None
    except (TypeError, ValueError, KeyError):
        price = None
    band = None if price is None else ("under ₹500" if price < 500 else "₹500–999" if price < 1000 else "₹1,000+")
    protection = int(direct_spf[0]) if direct_spf else int(spf[1]) if spf else None
    return {"spf": protection,
            "pa": "PA" + pa[1] if pa else None, "formats": formats, "skin_types": skin_types,
            "ingredients": sorted(title_terms.intersection(INGREDIENTS)), "price_band": band,
            "size": product.get("size"), "price": price}
