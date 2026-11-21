"""Cut out actual PDP packshots and render the supplied typography as HTML."""

from __future__ import annotations

import os
import shutil
from hashlib import sha256
from html import escape
from pathlib import Path
from statistics import median

from PIL import Image, ImageDraw, ImageFilter

# Art-directed silhouette sampled from this immutable 80 ml product photograph.
# This excludes the annotation stickers touching the pack. Vertices are 400px coordinates.
HERO_SHA = "4af297e6329f6def1bfa457447bf5df588c27ffdbf05462acb26a667c8c25e08"
HERO_OUTLINE = [
    (138, 115),
    (144, 108),
    (152, 103),
    (163, 99),
    (176, 96),
    (190, 95),
    (204, 96),
    (216, 99),
    (227, 104),
    (235, 111),
    (241, 121),
    (245, 134),
    (265, 246),
    (272, 278),
    (277, 314),
    (277, 331),
    (274, 344),
    (269, 354),
    (260, 362),
    (249, 364),
    (175, 375),
    (165, 371),
    (156, 364),
    (149, 356),
    (144, 346),
    (141, 334),
    (138, 312),
    (136, 291),
    (128, 160),
    (128, 138),
    (130, 129),
    (133, 122),
]
SIZES = [
    ("meta-square", "Meta feed", 1080, 1080),
    ("meta-portrait", "Meta portrait", 1080, 1350),
    ("meta-story", "Meta Stories", 1080, 1920),
    ("display-rectangle", "Google Display rectangle", 300, 250),
    ("display-leaderboard", "Google Display leaderboard", 728, 90),
    ("display-landscape", "Google Display landscape", 1200, 628),
    ("amazon-banner", "Amazon Sponsored Brands creative", 1200, 628),
    ("flipkart-banner", "Flipkart banner draft", 1200, 400),
    ("nykaa-banner", "Nykaa banner draft", 1440, 480),
]


def cutout(root, brief):
    images = brief["product"]["local_images"]
    if not images:
        return None, {"status": "unavailable", "reason": "No official image downloaded"}
    source = Path(root) / images[0]
    im = Image.open(source).convert("RGB")
    target = Path(root) / "inputs/cutout.png"
    if sha256(source.read_bytes()).hexdigest() == HERO_SHA:
        mask = Image.new("L", im.size)
        coords = [
            (round(x * im.width / 400), round(y * im.height / 400))
            for x, y in HERO_OUTLINE
        ]
        ImageDraw.Draw(mask).polygon(coords, fill=255)
        im.putalpha(mask.filter(ImageFilter.GaussianBlur(0.7)))
        im = im.crop(im.getbbox())
        method = "Verified product silhouette from the original Shopify packshot"
    else:
        try:
            from rembg import new_session, remove

            im = remove(
                im, session=new_session("u2netp", providers=["CPUExecutionProvider"])
            )
            im = im.crop(im.getbbox())
            method = "rembg U2NetP on the official primary product shot"
        except (ImportError, OSError, RuntimeError, ValueError):
            return images[0], {
                "status": "source_photo",
                "method": "Original Shopify photograph",
                "source": images[0],
            }
    im.save(target)
    return "inputs/cutout.png", {
        "status": "cutout",
        "method": method,
        "source": images[0],
    }


def _relative_url(path, root, folder):
    return (
        os.path.relpath(Path(root) / path, folder).replace(os.sep, "/") if path else ""
    )


def ad_html(root, folder, brief, size, asset, bg, headline, support, cta, platform):
    w, h = size
    portrait = h > w * 1.1
    strip = w / h > 4
    palette = brief["brand_kit"]["colors"]
    ink = next(
        (v for v in palette if v.lower() in ("#0a0a0a", "#191919", "#000000")),
        "#191919",
    )
    tint = palette[1] if len(palette) > 2 else "#ffdee5"

    def url(path):
        return escape(_relative_url(path, root, folder), quote=True)

    fonts = "".join(
        "@font-face{font-family:Brand;src:url('%s');font-weight:%d}"
        % (url(font["path"]), font["weight"])
        for font in brief["brand_kit"]["font_files"]
    )
    brand = (
        (
            "<img class='logo' alt='Dot &amp; Key' src='"
            + url(brief["brand_kit"]["logo"])
            + "'>"
        )
        if brief["brand_kit"].get("logo")
        else "<b class='logo'>Dot &amp; Key</b>"
    )
    # Fixed-pixel deliverables need different composition for each aspect ratio.
    if strip:
        layout = f".logo{{width:{w * 0.108}px}} .copy{{left:4%;top:12%;width:66%;height:80%;justify-content:center}} h1{{font-size:{h * 0.28}px;margin:2px 0}} .support,.cta{{display:none}} .pack{{height:88%;right:12%;bottom:3%}}"
    elif portrait:
        layout = f".logo{{width:40%}} .copy{{left:8%;top:6%;width:80%;height:44%}} h1{{font-size:{w * 0.10}px;max-width:90%}} .support{{font-size:{w * 0.030}px;max-width:86%}} .pack{{height:45%;right:14%;bottom:4%}} .cta{{font-size:{w * 0.024}px}}"
    else:
        layout = f".logo{{width:35%}} .copy{{left:7%;top:8%;width:52%;height:82%;justify-content:center}} h1{{font-size:{min(w * 0.080, h * 0.137):.2f}px}} .support{{font-size:{min(w * 0.025, h * 0.039):.2f}px}} .cta{{font-size:{min(w * 0.021, h * 0.035):.2f}px}} .pack{{height:78%;right:8%;bottom:8%}}"
    if 0.92 <= w / h <= 1.08:
        layout += ".pack{height:72%;right:5.5%;bottom:9%}"
    control = "" if not cta else f"<span class='cta'>{escape(cta)}</span>"
    image = (
        f"<img class='pack' src='{url(asset)}' alt='Original product photograph'>"
        if asset
        else ""
    )
    scene = (
        f"background-image:linear-gradient(90deg,rgba(255,248,245,.84) 0%,rgba(255,248,245,.52) 38%,transparent 80%),url('{url(bg)}');"
        if bg
        else ""
    )
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{escape(platform)}</title><style>
    {fonts}*{{box-sizing:border-box}}html,body{{width:{w}px;height:{h}px;margin:0;overflow:hidden}}
    body{{position:relative;background:{tint};{scene}background-size:cover;background-position:center;font-family:Brand,Arial,sans-serif;color:{ink}}}
    .copy{{position:absolute;display:flex;flex-direction:column;align-items:flex-start;z-index:2}}
    .logo{{display:block;max-height:17%;object-fit:contain;object-position:left}}
    h1{{line-height:1.04;letter-spacing:-.065em;margin:.34em 0 .18em;font-weight:700;text-wrap:balance}}
    .support{{line-height:1.32;max-width:95%;font-weight:400;margin:0}}
    .cta{{display:inline-block;background:{ink};color:white;border-radius:3em;padding:.50em 1.1em;margin-top:1em;font-weight:500}}
    .pack{{object-fit:contain;position:absolute;transform:rotate(5deg);filter:drop-shadow(.4vw 1vw .8vw rgba(66,25,28,.23))}}
    {layout}</style><main><div class="copy">{brand}<h1>{escape(headline)}</h1><p class="support">{escape(support)}</p>{control}</div>{image}</main></html>"""


def browser_launch(playwright):
    options = {"args": ["--allow-file-access-from-files"]}
    if path := os.getenv("STUDIO_CHROME_BIN"):
        options["executable_path"] = path
    else:
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            shutil.which("chromium"),
            shutil.which("google-chrome"),
        ):
            if candidate and Path(candidate).exists():
                options["executable_path"] = candidate
                break
    return playwright.chromium.launch(**options)


def render_templates(root, templates, brief):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = browser_launch(pw)
        try:
            for item, html in templates:
                w, h = item["size"]
                dest = Path(root) / item["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                source = dest.with_suffix(".html")
                source.write_text(html)
                page = browser.new_page(
                    viewport={"width": w, "height": h}, device_scale_factor=1
                )
                try:
                    page.goto(source.resolve().as_uri(), wait_until="load")
                    page.evaluate("document.fonts.ready")
                    measured = page.evaluate("""() => {
                      const box=e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]};
                      return {pack:!!Array.from(document.images).find(i=>i.classList.contains('pack')&&i.naturalWidth>0),logo:!!Array.from(document.images).find(i=>i.classList.contains('logo')&&i.naturalWidth>0),
                        images:Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0),
                        bounds:Array.from(document.querySelectorAll('h1,h2,.support,.cta,.caption,.compare')).filter(e=>getComputedStyle(e).display!=='none').map(box),
                        font:document.fonts.check('700 16px Brand')};
                    }""")
                    page.screenshot(path=str(dest), animations="disabled")
                finally:
                    page.close()
                visible = all(
                    v[0] >= -1 and v[1] >= -1 and v[2] <= w + 1 and v[3] <= h + 1
                    for v in measured["bounds"]
                )
                with Image.open(dest) as im:
                    observed = im.convert("RGB").resize((90, 90)).getdata()
                    colors = [
                        tuple(bytes.fromhex(c.lstrip("#")))
                        for c in brief["brand_kit"]["colors"]
                        if len(c) == 7
                    ]
                    distances = (
                        [
                            min(
                                sum((a - b) ** 2 for a, b in zip(px, color)) ** 0.5
                                for color in colors
                            )
                            for px in observed
                        ]
                        if colors
                        else []
                    )
                    distance = round(median(distances), 2) if distances else None
                    share = (
                        round(sum(d <= 75 for d in distances) / len(distances), 3)
                        if distances
                        else 0
                    )
                if item["kind"] in ("static", "A+ header"):
                    item["checks"].append(
                        {
                            "id": "real-packshot",
                            "label": "Original catalog product photograph loaded",
                            "status": "pass" if measured["pack"] else "fail",
                        }
                    )
                item["checks"].extend(
                    [
                        {
                            "id": "layout",
                            "label": "Text in frame and all images loaded",
                            "status": "pass"
                            if visible and measured["images"]
                            else "fail",
                        },
                        {
                            "id": "logo",
                            "label": "Official logo loaded",
                            "status": "pass" if measured["logo"] else "warn",
                        },
                        {
                            "id": "palette",
                            "label": "Palette coverage across 8,100 sampled pixels",
                            "median_rgb_distance": distance,
                            "share_within_75_rgb_units": share,
                            "threshold": "35% of sampled pixels within 75 RGB units of an official swatch",
                            "distance": distance,
                            "status": "pass" if share >= 0.35 else "warn",
                        },
                        {
                            "id": "type",
                            "label": "Brand font loaded",
                            "status": "pass"
                            if brief["brand_kit"]["font_files"] and measured["font"]
                            else "warn",
                        },
                    ]
                )
                item["source_html"] = str(source.relative_to(root))
                item["status"] = (
                    "fail"
                    if any(c["status"] == "fail" for c in item["checks"])
                    else "ready"
                )
        finally:
            browser.close()


# Verified crops are tied to the bytes of each official photo. A changed photograph never inherits old coordinates.
CROPS = {
    HERO_SHA: [("fruit", (0.745, 0.37, 0.816, 0.62))],
    "52528c69131f49ce6787047f5ba78f0f8d2da8986d723615a3f506a764fcc41c": [
        ("texture", (0.52, 0.56, 0.87, 0.85)),
        ("fruit", (0.652, 0.258, 1, 0.62)),
    ],
    "e0994c64c26224c80ff95f3a34f2ca66110a124c8ee7e5da9f8fbe29234f1f89": [
        ("presenter", (0.445, 0.18, 1, 1))
    ],
}


def detail_photos(root, brief):
    result = {}
    for rel in brief["product"]["local_images"]:
        source = Path(root) / rel
        for label, (l, t, r, b) in CROPS.get(
            sha256(source.read_bytes()).hexdigest(), []
        ):
            with Image.open(source) as image:
                crop = image.crop(
                    (
                        round(l * image.width),
                        round(t * image.height),
                        round(r * image.width),
                        round(b * image.height),
                    )
                )
                dest = f"inputs/detail-{label}.jpg"
                crop.save(Path(root) / dest, quality=92)
            result[label] = {"path": dest, "source": rel, "crop": [l, t, r, b]}
    return result


def verified_background(root, path):
    """Replace the isolated sticker area in the known generated plate with the same wall gradient."""
    if not path:
        return None, None
    source = Path(root) / path
    if sha256(source.read_bytes()).hexdigest() != VERIFIED_PLATE_SHA:
        return path, None
    dest = source.with_name(source.stem + "-clean.jpg")
    if not dest.exists():
        import numpy as np

        frame = np.asarray(Image.open(source).convert("RGB")).astype(float)
        h, w = frame.shape[:2]
        left, right, top, bottom = (
            int(0.58 * w),
            int(0.84 * w),
            int(0.18 * h),
            int(0.307 * h),
        )
        blend = np.linspace(0, 1, right - left)[None, :, None]
        band = (
            frame[top:bottom, left - 3 : left].mean(axis=1, keepdims=True) * (1 - blend)
            + frame[top:bottom, right : right + 3].mean(axis=1, keepdims=True) * blend
        )
        mask = Image.new("L", (w, h))
        draw = ImageDraw.Draw(mask)
        draw.rectangle((left + 9, top + 9, right - 9, bottom - 9), fill=255)
        alpha = (
            np.asarray(mask.filter(ImageFilter.GaussianBlur(4.5)))[
                top:bottom, left:right, None
            ]
            / 255
        )
        frame[top:bottom, left:right] = (
            frame[top:bottom, left:right] * (1 - alpha) + band * alpha
        )
        Image.fromarray(frame.astype("uint8")).save(dest, quality=90)
    return str(dest.relative_to(root)), {
        "method": "Removed a generated sticker by reconstructing the surrounding gradient.",
        "source": path,
    }


VERIFIED_PLATE_SHA = "32888aefb2087986ddd43904a80fd401ef5fa5b3e5b39f8352cba0e22ee9a145"
