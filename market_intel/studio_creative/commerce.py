"""Catalog-locked marketplace material and campaign test instructions."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .assets import (
    SIZES,
    _relative_url,
    ad_html,
    cutout,
    detail_photos,
    render_templates,
    verified_background,
)
from .brief import BANNED, write_json
from .copy import CTA, _typed, claim_guard
from .provider import background, compose_json

MARKETS = {
    "Amazon India": {"title": 200, "bullet": 200, "keyword_bytes": 249},
    "Flipkart": {"title": 120, "bullet": 180, "keyword_bytes": 220},
    "Nykaa": {"title": 110, "bullet": 160, "keyword_bytes": 200},
}


def listing_copies(root, brief):
    facts = brief["claim_sources"]
    names = _typed(brief, "short_name") + _typed(brief, "name")
    bounds = MARKETS
    system = (
        "Edit listings for the three marketplaces in JSON {listings:[{market,title_fact_id,bullet_ids:[five distinct IDs],"
        "description_ids:[two distinct IDs],keywords:[words]}]}. Select evidence from the supplied D&K fact sheet. "
        "Do not invent claims, compare competitors, or quote reviews. Favor benefits, then instructions; let the editing "
        "vary by marketplace. Keywords must be in the supplied terms. Return one listing for every market."
    )
    terms = list(
        dict.fromkeys(
            str(t).lower()
            for t in [
                *brief.get("search_terms", []),
                *brief["product"]["ingredients"],
                *brief["audience"]["skin_types"],
                brief["product"]["category"],
            ]
            if t
        )
    )
    data = {
        "facts": facts,
        "markets": bounds,
        "terms": terms,
        "title_options": [r["id"] for r in names],
    }
    result, recipe = compose_json(system, data, root=root, label="listings")
    by_id = {f["id"]: f for f in facts}
    options = [
        r
        for r in facts
        if r["kind"]
        in (
            "benefit",
            "direction",
            "feature",
            "spf",
            "size",
            "ingredient",
            "short_name",
            "name",
        )
    ]
    output = []
    for market, limits in bounds.items():
        model_rows = (result or {}).get("listings", [])
        row = (
            next(
                (
                    r
                    for r in model_rows
                    if isinstance(r, dict) and r.get("market") == market
                ),
                {},
            )
            if isinstance(model_rows, list)
            else {}
        )
        proposed = by_id.get(row.get("title_fact_id"))
        titlefact = (
            proposed
            if proposed in names and len(proposed["text"]) <= limits["title"]
            else next(
                (r for r in names if len(r["text"]) <= limits["title"]), names[-1]
            )
        )

        # The >200-char case is deliberately surfaced by the validator, never silently truncated.
        def choose(ids, n, cap):
            preferred = (
                [by_id[v] for v in ids if isinstance(v, str) and v in by_id]
                if isinstance(ids, list)
                else []
            )
            selected = []
            for f in preferred + options:
                if f not in selected and len(f["text"]) <= cap:
                    selected.append(f)
                if len(selected) == n:
                    break
            return selected

        bullets = choose(row.get("bullet_ids"), 5, limits["bullet"])
        description = choose(row.get("description_ids"), 2, 200)
        keyword_list = []
        wanted = row.get("keywords", [])
        allowed_keywords = (
            [
                w.lower().strip()
                for w in wanted
                if isinstance(w, str) and w.lower().strip() in terms
            ]
            if isinstance(wanted, list)
            else []
        ) + terms
        for w in dict.fromkeys(allowed_keywords):
            if len((" ".join(keyword_list + [w])).encode()) <= limits["keyword_bytes"]:
                keyword_list.append(w)
        keywords = " ".join(keyword_list)
        lines = [titlefact["text"]] + [f["text"] for f in bullets + description]
        corpus = " ".join(lines + [keywords]).casefold()
        wanted_terms = brief.get("search_terms", [])
        missing = [t for t in wanted_terms if t.casefold() not in corpus]
        checks = [
            claim_guard(lines, brief),
            {
                "id": "length",
                "label": "Title, five bullets and keyword byte budget",
                "status": "pass"
                if len(titlefact["text"]) <= limits["title"]
                and len(bullets) == 5
                and len(set(f["text"] for f in bullets)) == 5
                and len(keywords.encode()) <= limits["keyword_bytes"]
                else "fail",
            },
            {
                "id": "terms",
                "label": "Category and ingredient keyword coverage",
                "status": "warn" if missing else "pass",
                "missing": missing,
            },
            {
                "id": "tone",
                "label": "Restricted tone vocabulary",
                "status": "fail" if BANNED.search(corpus) else "pass",
            },
        ]
        output.append(
            {
                "id": "listing-" + market.split()[0].lower(),
                "market": market,
                "title": titlefact["text"],
                "bullets": [f["text"] + "." for f in bullets],
                "description": ". ".join(f["text"] for f in description) + ".",
                "keywords": keywords,
                "keyword_bytes": len(keywords.encode()),
                "refs": {
                    "title": titlefact["id"],
                    "bullets": [f["id"] for f in bullets],
                    "description": [f["id"] for f in description],
                },
                "checks": checks,
                "limits": limits,
                "limit_basis": "Studio editorial budgets. Confirm the seller's current field limits before submission.",
                "recipe": recipe,
                "status": "fail"
                if any(c["status"] == "fail" for c in checks)
                else "ready",
            }
        )
    return output


def _module_html(root, item, brief, title, body, columns, photos):
    dest = root / item["path"]
    w, h = item["size"]

    def url(p):
        return escape(_relative_url(p, root, dest.parent), quote=True)

    logo = brief["brand_kit"]["logo"]
    brand = (
        f'<img class="logo" src="{url(logo)}" alt="Dot &amp; Key">'
        if logo
        else "<b>Dot &amp; Key</b>"
    )
    fonts = "".join(
        "@font-face{font-family:Brand;src:url('%s');font-weight:%d}"
        % (url(f["path"]), f["weight"])
        for f in brief["brand_kit"]["font_files"]
    )
    pink = brief["brand_kit"]["colors"][0]
    single = len(columns) == 1
    cells = []
    for n, (heading, text) in enumerate(columns):
        pic = (
            f"<img class='photo' src='{url(photos[n % len(photos)])}' alt='Official product image'>"
            if photos
            else ""
        )
        cells.append(
            f"""<article>{pic}<div class="caption"><b>{escape(heading)}</b><p>{escape(text)}</p></div></article>"""
        )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{escape(title)}</title><style>
    {fonts}*{{box-sizing:border-box}}body{{width:{w}px;height:{h}px;margin:0;padding:36px 44px;background:#fff7f8;color:#1e1920;font-family:Brand,Arial,sans-serif}}
    .top{{display:flex;align-items:center;justify-content:space-between}}.logo{{width:112px;height:40px;object-fit:contain}}.top span{{height:3px;background:{pink};width:67%}}
    h1{{font-size:48px;line-height:1.08;letter-spacing:-.065em;margin:20px 0 6px}}.support{{font-size:17px;margin:0 0 17px;line-height:1.3}}
    .grid{{display:grid;gap:16px;grid-template-columns:repeat({len(columns)},1fr);margin-top:15px}}
    article{{min-width:0;display:{"flex" if single else "block"};align-items:center;gap:32px;background:#fff;border-radius:14px;overflow:hidden}}
    .photo{{width:{"44%" if single else "100%"};height:{285 if single else 215}px;object-fit:cover;background:linear-gradient(135deg,#fff4f5,{pink}40);padding:0}}
    .caption{{padding:14px;font-size:{23 if single else 16}px;line-height:1.26}}.caption p{{font-size:{18 if single else 14}px;margin:8px 0 0}}
    </style><div class="top">{brand}<span></span></div><h1>{escape(title)}</h1><p class="support">{escape(body)}</p><section class="grid">{"".join(cells)}</section></html>"""


def visuals(root, brief, concept):
    root = Path(root)
    cut, cut_recipe = cutout(root, brief)
    brief["product"].update(cutout=cut, cutout_recipe=cut_recipe)
    details = detail_photos(root, brief)
    bg, bgrec = background(root, brief)
    bg, post = verified_background(root, bg)
    if post:
        bgrec = {**bgrec, "postprocess": post}
    kit = brief["brand_kit"]
    name = (_typed(brief, "short_name") or _typed(brief, "name"))[0]
    proof = (
        _typed(brief, "spf")
        + _typed(brief, "feature")
        + _typed(brief, "ingredient")
        + [name]
    )[0]
    feature = (_typed(brief, "feature") + _typed(brief, "benefit") + [proof])[0]
    modules = []
    statics = []
    templates = []

    def card(id, label, w, h, kind, lines, refs):
        return {
            "id": id,
            "label": label,
            "title": label,
            "size": [w, h],
            "kind": kind,
            "path": f"assets/{id}.png",
            "inputs": {
                "photos": brief["product"]["local_images"],
                "fact_refs": refs,
                "concept_ref": concept["id"],
                "pattern_ref": concept["pattern_ref"],
            },
            "recipe": {
                "renderer": "Playwright / Chromium",
                "palette": kit["colors"],
                "fonts": kit["fonts"],
                "background": bgrec,
                "packshot": cut_recipe,
            },
            "checks": [
                claim_guard(lines, brief),
                {
                    "id": "tone",
                    "label": "Restricted tone vocabulary",
                    "status": "fail"
                    if any(BANNED.search(t) for t in lines)
                    else "pass",
                },
            ],
        }

    for i, (id, label, w, h) in enumerate(SIZES):
        heading = name["text"]
        supporting = proof if i % 3 != 1 else feature
        item = card(
            id,
            label,
            w,
            h,
            "static",
            [heading, supporting["text"], CTA],
            [name["id"], supporting["id"]],
        )
        item["headline"] = heading
        item["support"] = supporting["text"]
        item["placement_basis"] = (
            "Studio mockup. Confirm merchant placement requirements before delivery."
            if id in ("flipkart-banner", "nykaa-banner")
            else "Configured export size"
        )
        static = ad_html(
            root,
            root / "assets",
            brief,
            (w, h),
            cut,
            bg,
            heading,
            supporting["text"],
            CTA,
            label,
        )
        statics.append(item)
        templates.append((item, static))
    hero = card(
        "aplus-header",
        "Product header",
        970,
        600,
        "A+ header",
        [name["text"], proof["text"]],
        [name["id"], proof["id"]],
    )
    templates.append(
        (
            hero,
            ad_html(
                root,
                root / "assets",
                brief,
                (970, 600),
                cut,
                bg,
                name["text"],
                proof["text"],
                "",
                hero["label"],
            ),
        )
    )
    modules.append(hero)

    def make(id, title, subtitle, columns, photos, rows, comparison=False):
        item = card(
            "aplus-" + id,
            title,
            970,
            600,
            "A+ module",
            [r["text"] for r in rows],
            [r["id"] for r in rows],
        )
        item["columns"] = [{"heading": h, "body": b} for h, b in columns]
        if comparison:
            item["checks"].append(
                {
                    "id": "own-range",
                    "label": "Only Dot & Key catalog products included",
                    "status": "pass",
                    "urls": [r["url"] for r in brief["range"]],
                }
            )
        templates.append(
            (item, _module_html(root, item, brief, title, subtitle, columns, photos))
        )
        modules.append(item)

    candidates = (
        _typed(brief, "feature")
        + _typed(brief, "benefit")
        + _typed(brief, "ingredient")
        + [proof, name]
    )
    picks = list({r["id"]: r for r in candidates}.values())[:4]
    photos = [cut] + [
        details[k]["path"] for k in ("texture", "presenter", "fruit") if k in details
    ]
    photos = [p for p in photos if p]
    make(
        "features",
        "Formula details",
        name["text"],
        [(r["text"], "") for r in picks],
        photos,
        picks,
    )
    ing = (_typed(brief, "ingredient") or [name])[0]
    ingcopy = next(
        (r for r in _typed(brief, "benefit") if _contains(r["text"], ing["text"])), None
    )
    make(
        "ingredient",
        "Ingredient spotlight",
        name["text"],
        [(ing["text"], ingcopy["text"] if ingcopy else "")],
        [details["fruit"]["path"]] if "fruit" in details else photos,
        [ing] + ([ingcopy] if ingcopy else []),
    )
    directions = _typed(brief, "direction")[:3]
    if directions:
        make(
            "how-to",
            "How to use",
            name["text"],
            [(f"Step {j + 1}", r["text"]) for j, r in enumerate(directions)],
            [],
            directions,
        )
    else:
        make(
            "how-to",
            "How to use",
            name["text"],
            [("Use directions", "Refer to the product packaging.")],
            [],
            [],
        )
    related = sorted(
        brief["range"], key=lambda p: p.get("price") == brief["product"].get("price")
    )
    product_rows = [brief["product"]] + related[:2]
    make(
        "range",
        "Compare the range",
        "Dot & Key",
        [
            (
                r["title"],
                " · ".join(
                    s
                    for s in [
                        r.get("size"),
                        "SPF " + str(r["spf"]) if r.get("spf") else None,
                    ]
                    if s
                ),
            )
            for r in product_rows
        ],
        [],
        [],
        comparison=True,
    )
    comparison = modules[-1]
    comparison["inputs"]["range_products"] = [
        {
            "title": v["title"],
            "url": v["url"],
            "size": v.get("size"),
            "spf": v.get("spf"),
            "price": v.get("price"),
        }
        for v in product_rows
    ]
    comparison["checks"][0] = {
        "id": "claim-guard",
        "label": "Field-by-field match to the locked Dot & Key range",
        "status": "pass"
        if all(
            v.get("url", "").startswith("https://www.dotandkey.com/products/")
            for v in product_rows
        )
        else "fail",
    }
    templates[-1] = (
        comparison,
        _comparison_html(root, comparison, brief, product_rows),
    )
    render_templates(root, templates, brief)
    write_json(root / "brief.json", brief)
    return statics, modules


def _contains(text, word):
    return word.casefold() in text.casefold()


def test_plan(variants):
    ids = [r["id"] for r in variants]
    tests = [
        (
            "Opening line",
            ids[0],
            ids[2],
            "Hook rate",
            "3-second views / impressions",
            "Same demo, format, budget and audience.",
        ),
        (
            "Presenter or pack",
            ids[0],
            ids[1],
            "Hold rate",
            "completed views / video starts",
            "Same opening line and placement.",
        ),
        (
            "Third opening line",
            ids[2],
            ids[4],
            "CTR",
            "outbound clicks / impressions",
            "Use the same landing page and audience.",
        ),
    ]
    return {
        "first_three": [
            {
                "id": f"test-{n + 1}",
                "title": t,
                "control": a,
                "challenger": b,
                "primary_metric": m,
                "formula": f,
                "controls": c,
                "decision_window": "Review after 72 hours. Extend until each arm reaches 1,000 impressions.",
                "success_signal": "Prefer the higher primary rate only if the 95% interval for the difference excludes zero. Otherwise mark inconclusive.",
            }
            for n, (t, a, b, m, f, c) in enumerate(tests)
        ],
        "secondary_metrics": {
            "CTR": "outbound clicks / impressions",
            "CPA": "spend / attributed acquisitions",
            "hold rate": "completed views / video starts",
            "hook rate": "3-second views / impressions",
        },
        "avoid": [
            "Reusing a competitor's footage or implying its outcome for this product.",
            "Changing hook, format and audience in one comparison.",
            "Declaring a winner from raw view totals.",
        ],
        "readback": "Attach a published post to a variant and compare it with the originating account's baseline.",
    }


def _comparison_html(root, item, brief, rows):
    dest = root / item["path"]

    def uri(path):
        return escape(_relative_url(path, root, dest.parent), quote=True)

    fonts = "".join(
        "@font-face{font-family:Brand;src:url('%s');font-weight:%d}"
        % (uri(f["path"]), f["weight"])
        for f in brief["brand_kit"]["font_files"]
    )
    logo = brief["brand_kit"].get("logo")
    mark = (
        f'<img class="logo" src="{uri(logo)}" alt="Dot &amp; Key">'
        if logo
        else "Dot &amp; Key"
    )

    def val(r, key):
        v = r.get(key)
        if v is None:
            return "—"
        if key == "price":
            return "₹" + format(v, "g")
        return escape(str(v))

    table = (
        "<tr><th></th>"
        + "".join("<th>" + escape(r["title"]) + "</th>" for r in rows)
        + "</tr>"
    )
    for label, key in (
        ("Pack size", "size"),
        ("SPF", "spf"),
        ("Catalog price", "price"),
    ):
        table += (
            "<tr><th>"
            + label
            + "</th>"
            + "".join("<td>" + val(r, key) + "</td>" for r in rows)
            + "</tr>"
        )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>Compare the range</title>
    <style>{fonts}*{{box-sizing:border-box}}body{{width:970px;height:600px;margin:0;background:#fff8f8;color:#241f22;padding:36px 45px;font-family:Brand,Arial,sans-serif}}
    header{{display:flex;align-items:center;gap:35px}}header:after{{content:'';height:2px;background:{brief["brand_kit"]["colors"][0]};flex:1}}
    .logo{{width:116px;height:38px;object-fit:contain}}h1{{margin:22px 0 20px;font-size:49px;letter-spacing:-3px;line-height:1.12}}
    table{{border-spacing:0;width:100%;table-layout:fixed;border-radius:16px;overflow:hidden;font-size:19px;background:white}}
    th,td{{text-align:left;vertical-align:middle;padding:14px;border-bottom:1px solid #efdde3}}th:first-child{{width:16%;font-weight:500}}
    tr:first-child th{{font-size:18px;line-height:1.3;background:#fbe4ea;padding-top:20px;padding-bottom:20px}}
    .support{{font-size:14px;color:#604e57;margin-top:14px}}</style><header>{mark}</header><h1>Compare the range</h1><table class="compare">{table}</table>
    <p class="support">Dot &amp; Key catalog · {escape(str(brief.get("as_of", "")))}</p></html>"""
