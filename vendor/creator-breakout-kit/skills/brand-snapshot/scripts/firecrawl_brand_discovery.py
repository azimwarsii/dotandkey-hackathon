#!/usr/bin/env python3
import argparse
import json
import os
import re
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

API_BASE = "https://api.firecrawl.dev/v1"
ROOT = Path(__file__).resolve().parents[3]

KEYWORDS = {
    "founder": ["about", "story", "founder", "our-story", "our_story", "who-we-are", "about-us"],
    "product": ["product", "products", "shop", "collection", "collections"],
    "routine": ["routine", "how-to", "how_to", "guide", "usage", "use", "regimen"],
    "faq": ["faq", "faqs", "questions", "help"],
    "press": ["press", "retailer", "stockist", "stores", "reviews"],
}
PRODUCT_SCORE_THRESHOLD = 50


def ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def load_dotenv(path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_firecrawl_key():
    load_dotenv(ROOT / ".env")
    if os.getenv("FIRECRAWL_API_KEY"):
        return os.getenv("FIRECRAWL_API_KEY")
    raise RuntimeError("FIRECRAWL_API_KEY not found. Add it to creator-breakout-kit/.env or export it in your shell.")


def api_request(path, payload=None, method="POST"):
    key = load_firecrawl_key()
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = Request(
        f"{API_BASE}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urlopen(req, timeout=20, context=ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize_url(url):
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def safe_slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def map_site(url, limit=50):
    payload = {"url": url, "limit": limit, "includeSubdomains": False}
    try:
        resp = api_request("/map", payload)
        data = resp.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "links" in data and isinstance(data["links"], list):
                return data["links"]
            if "urls" in data and isinstance(data["urls"], list):
                return data["urls"]
        return []
    except Exception:
        return []


def score_url(url):
    path = urlparse(url).path.lower().strip("/")
    if not path:
        return "homepage", 100

    segments = [seg for seg in path.split("/") if seg]
    score = 0
    page_type = "other"

    if any(k in path for k in ["about", "story", "founder", "our-story", "about-us"]):
        return "founder", 90
    if any(k in path for k in ["faq", "faqs", "help", "questions"]):
        return "faq", 80
    if any(k in path for k in ["routine", "how-to", "guide", "regimen", "use"]):
        return "routine", 75
    if any(k in path for k in ["press", "reviews", "stockist", "retailer", "stores"]):
        return "press", 70
    if any(k in path for k in ["best-sellers", "bestsellers", "featured", "collections/all"]):
        return "product", 68
    if any(k in path for k in ["product", "products", "shop", "collection", "collections"]):
        score = 55
        page_type = "product"

    # Generic weak signals that usually mean "not a primary product page worth crawling"
    weak_terms = [
        "gift-card",
        "giftcards",
        "accessories",
        "bundle-builder",
        "refill",
        "replacement",
    ]
    if page_type == "product":
        # A collection URL with a specific category slug (e.g. /collections/{category}) is usually a
        # real product category page, not the generic /collections/all.
        if any(k in path for k in ["collections", "collection"]) and len(segments) >= 2:
            score += 12
        if any(k in path for k in weak_terms):
            score -= 35

    return page_type, score


def extract_links_from_markdown(markdown, base_url):
    links = []
    for match in re.findall(r"\((https?://[^)\s]+)\)", markdown or ""):
        if match.startswith(base_url):
            links.append(match)
    return sorted(set(links))


def choose_urls(base_url, mapped_urls):
    selected = {"homepage": base_url}
    buckets = {k: [] for k in KEYWORDS.keys()}
    for raw in mapped_urls:
        url = raw["url"] if isinstance(raw, dict) and "url" in raw else raw
        if not isinstance(url, str):
            continue
        if not url.startswith(base_url):
            continue
        page_type, score = score_url(url)
        if score <= 0:
            continue
        if page_type not in buckets:
            continue
        buckets[page_type].append((score, url))

    for page_type, candidates in buckets.items():
        candidates = sorted(set(candidates), key=lambda x: (-x[0], len(x[1])))
        if candidates:
            selected[page_type] = candidates[0][1]

    product_candidates = sorted(set(buckets.get("product", [])), key=lambda x: (-x[0], len(x[1])))
    product_candidates = [item for item in product_candidates if item[0] >= PRODUCT_SCORE_THRESHOLD]
    selected["product_pages"] = [u for _, u in product_candidates[:2]] if product_candidates else []
    return selected


def scrape(url):
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True,
        "waitFor": 1500,
    }
    try:
        resp = api_request("/scrape", payload)
        data = resp.get("data", {})
        md = data.get("markdown", "")
        meta = data.get("metadata", {})
        return {
            "url": url,
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "markdown": md,
        }
    except Exception as e:
        return {"url": url, "error": str(e), "markdown": "", "title": "", "description": ""}


def extract_price_points(text):
    raw = re.findall(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text)
    all_prices = []
    filtered = []
    suspicious = []
    for price in raw:
        numeric = float(price.replace("$", "").replace(",", ""))
        all_prices.append((numeric, price))
        if numeric > 1000:
            suspicious.append(price)
        elif numeric >= 20:
            filtered.append(price)

    def dedupe_sorted(prices):
        return sorted(set(prices), key=lambda p: float(p.replace("$", "").replace(",", "")))

    return {
        "raw": dedupe_sorted([p for _, p in all_prices])[:30],
        "filtered": dedupe_sorted(filtered)[:20],
        "suspicious": dedupe_sorted(suspicious)[:10],
    }


def clean_markdown_line(line):
    line = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", line)
    line = re.sub(r"<[^>]+>", " ", line)
    line = re.sub(r"\[([^\]]*)\]\([^\)]+\)", r"\1", line)
    line = re.sub(r"\|", " ", line)
    line = re.sub(r"[\u203a\u00bb\u2192]", " ", line)
    line = re.sub(r"\s+", " ", line).strip(" -•\t")
    return line


def is_commerce_fragment(line):
    lower = line.lower()
    if lower.count("shop") >= 2:
        return True
    if "shop" in lower and any(t in lower for t in ["best sellers", "best-sellers", "new arrivals", "sale"]):
        return True
    if any(token in lower for token in ["add to cart", "add to bag", "sold out"]):
        return True
    return False


def extract_verbatim(text):
    lines = [clean_markdown_line(l) for l in text.splitlines() if l.strip()]
    noise = [
        "skip to content",
        "toggle",
        "add to bag",
        "search",
        "reload",
        "blocked by an extension",
        "picture-in-picture",
        "free ground shipping",
        "shop now",
        "view details",
        "sold out",
        "add to cart",
        "starter set",
        "free shipping",
    ]
    strong = []
    seen = set()
    for line in lines:
        lower = line.lower()
        if not line:
            continue
        if any(n in lower for n in noise):
            continue
        if is_commerce_fragment(line):
            continue
        if line.startswith("#"):
            continue
        if line in seen:
            continue
        if 35 <= len(line) <= 220:
            seen.add(line)
            strong.append(line)
    return strong[:12]


def summarize(scraped, brand_name):
    combined = "\n\n".join(p.get("markdown", "") for p in scraped if p.get("markdown"))
    founder = next((p for p in scraped if "founder" in p.get("role", "")), None)
    homepage = next((p for p in scraped if p.get("role") == "homepage"), None)
    product_pages = [p for p in scraped if p.get("role") == "product"]
    prices = extract_price_points(combined)

    return {
        "brand_name": brand_name,
        "brand_summary": (homepage or {}).get("description", "") or (homepage or {}).get("title", ""),
        "hero_products": [re.sub(r"\s+", " ", p.get("title", "")).strip() for p in product_pages if p.get("title")][:5],
        "price_points": prices["filtered"],
        "suspicious_price_points": prices["suspicious"],
        "raw_price_points": prices["raw"],
        "founder_positioning": (founder or {}).get("title", "") or "",
        "audience_hypothesis": "Derived from brand copy and product positioning; verify against real buyer data before final briefing.",
        "primary_desires": [],
        "primary_objections": [],
        "proof_points": [],
        "claim_risks": [],
        "source_coverage_notes": [p.get("url") for p in scraped],
        "verbatim_language": extract_verbatim(combined),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand-name", required=True)
    ap.add_argument("--brand-url", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    brand_url = normalize_url(args.brand_url)
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    homepage_doc = scrape(brand_url)
    homepage_doc["role"] = "homepage"

    mapped = map_site(brand_url)
    homepage_links = extract_links_from_markdown(homepage_doc.get("markdown", ""), brand_url)
    candidate_urls = mapped if mapped else homepage_links
    chosen = choose_urls(brand_url, candidate_urls)

    scrape_targets = [("homepage", chosen["homepage"])]
    for key in ["founder", "routine", "faq", "press"]:
        if key in chosen:
            scrape_targets.append((key, chosen[key]))
    for url in chosen.get("product_pages", [])[:2]:
        scrape_targets.append(("product", url))

    scraped = []
    seen_urls = set()
    for role, url in scrape_targets:
        if url in seen_urls:
            continue
        if role == "homepage":
            doc = homepage_doc
        else:
            doc = scrape(url)
        seen_urls.add(url)
        doc["role"] = role
        scraped.append(doc)
        time.sleep(0.3)

    summary = summarize(scraped, args.brand_name)

    raw_path = os.path.join(out_dir, "firecrawl-pages.json")
    summary_path = os.path.join(out_dir, "brand-discovery.json")
    md_path = os.path.join(out_dir, "brand-discovery.md")

    with open(raw_path, "w") as f:
        json.dump({"mapped_urls": mapped, "homepage_links": homepage_links, "selected": chosen, "pages": scraped}, f, indent=2)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    with open(md_path, "w") as f:
        f.write(f"# Brand Discovery — {args.brand_name}\n\n")
        f.write(f"**Brand URL:** {brand_url}\n\n")
        f.write("## Source Coverage\n")
        for p in scraped:
            f.write(f"- `{p['role']}` — {p['url']}\n")
        f.write("\n## Hero Products\n")
        for hp in summary["hero_products"]:
            f.write(f"- {hp}\n")
        f.write("\n## Price Points\n")
        for pp in summary["price_points"]:
            f.write(f"- {pp}\n")
        if summary.get("suspicious_price_points"):
            f.write("\n## Suspicious Price Points\n")
            for pp in summary["suspicious_price_points"]:
                f.write(f"- {pp}\n")
        f.write("\n## Verbatim Language Worth Preserving\n")
        for line in summary["verbatim_language"]:
            f.write(f"- {line}\n")

    print(json.dumps({
        "raw_path": raw_path,
        "summary_path": summary_path,
        "markdown_path": md_path,
        "pages_scraped": len(scraped),
    }))


if __name__ == "__main__":
    main()
