# Part 1 Plan: Catalog, Marketplace, Review and Competitor Collection

> **Status: design plan, written before the build.** For how the system actually works now, see [architecture.md](architecture.md). For commands, see the [README](../README.md).

Scope: the data-collection layer of the Dot & Key brief. It covers extracting the catalog, finding each product on marketplaces, collecting price, rating and reviews, picking the top 5 competitors per category, and gathering brand-level signals. Sentiment, SWOT, gaps and content generation consume this layer's output and are not covered here.

---

## 0. What recon already confirmed (21 Nov)

| Source | Method | Result |
|---|---|---|
| dotandkey.com catalog | Shopify `GET /products.json?limit=250&page=N` | **Works.** 148 products in one page, with title, handle, `body_html`, `product_type`, `tags`, variants (price, compare_at_price, sku), images and `published_at`. |
| Catalog taxonomy | `tags` | Filter tags such as `fltr_skin_concern_*`, `fltr_ingredients_*` and `fltr_dnk_new_arrival_*`. These give **concern and ingredient metadata for free**. |
| Catalog noise | `product_type` | 54 `Combo` and 27 `Free` (gift) items. **About 65 real single SKUs** in Moisturiser, Sunscreen, Face Wash, Serum, Lip Balm, Toner, Mask, Eye, Body and Hair. |
| D&K first-party reviews | Site uses **Judge.me** | Public widget endpoint, so on-site reviews are available per product handle without scraping. |
| Amazon.in search | plain server-side GET | **Works.** HTML contains `data-asin` for every result. |
| Flipkart search | plain server-side GET | **Works.** `reviewCount` is in the HTML. |
| Nykaa | plain server-side GET | **403.** Needs Crustdata `human_mode`, otherwise a fallback. |
| dotandkey.com product pages | rapid repeat GETs | **429.** Rate-limit our own requests and cache. |
| Competitor catalogs | Shopify `/products.json` on Minimalist, Foxtale, The Derma Co, Deconstruct, Plum, Re'equil, Pilgrim, Aqualogica, Mamaearth | **All work.** Full competitor catalogs, prices and launch dates at zero Crustdata cost. See Part 2 §6. |

These probes used curl from a laptop, not Crustdata. Crustdata `/web/enrich/live` also returns raw server-side HTML with **no JS rendering**, so it should behave the same way. **Spike 1 (below) confirms this with the real key.**

---

## 1. How Crustdata fits

Crustdata is a company, web and social data API, not an e-commerce scraper. We use it for three things:

| Need | Crustdata endpoint | Notes |
|---|---|---|
| Find marketplace listings and competitor products | `POST /web/search/live` with `query` + `site` (`amazon.in`, `flipkart.com`, `nykaa.com`), `location: "IN"` | About 10 results per page, 1 credit per page, 10 RPM |
| Fetch listing and review pages | `POST /web/enrich/live` with `urls[]` (≤10 per call) and `human_mode` | Raw HTML, 1 credit per URL, 10 RPM. **We write the parsers.** |
| Competitor discovery with a second opinion | `/web/search/live` with `sources: ["ai"]` | Deep-research answer plus references. Used to seed and validate the top-5 list. |
| Launch and news monitoring | `/web/search/live` with `sources: ["news"]`, `start_date` = 90 days ago | Detects "X launches new sunscreen" style stories |
| Social chatter | `/web/search/live` with `sources: ["social"]` or `site: reddit.com` | Reddit (r/IndianSkincareAddicts) threads, which we fetch afterwards |
| Brand-level competitor signals | `POST /company/enrich` by `domains` with `fields: [basic_info, web_traffic, followers, headcount, hiring, funding, news, competitors, seo, public_launches]` | 2 credits per brand. Shows momentum (traffic and follower growth), D2C push (hiring) and SEO overlap. |
| Brand launch posts | `POST /social_post/search` or `social_posts` field | Optional, costs +5 credits. Use only if the plan allows. |

Required headers on every call: `authorization: Bearer $CRUSTDATA_API_KEY`, `content-type: application/json`, `x-api-version: 2025-11-01`. Respect `X-RateLimit-Reset` on 429 and log `X-Credits-Used`.

---

## 2. Pipeline

```
[S1 Catalog] ──► [S2 Listing discovery] ──► [S3 Listing fetch+parse] ──► [S4 Reviews]
                        │                                                      │
                        ▼                                                      ▼
               [S5 Competitor set per category] ──► [S6 Brand signals] ──► [Store / API for Part 2]
```

### S1: Catalog extraction (no Crustdata)
- Page through `products.json` until it returns empty. Strip HTML from `body_html`.
- Normalize into a `Product` record: id, handle, title, category (derived from `product_type`), concerns and ingredients (parsed from `fltr_` tags), size (parsed from title or variant), price, MRP, images, `published_at`, is_new.
- Drop `Free`. Keep `Combo` but link it to its component SKUs and exclude it from competitor analysis.
- Use a cheap model via **OpenRouter** (Gemini Flash or Claude Haiku) to fill gaps such as hero ingredient, SPF, skin type and size when tags are missing. This is cheap, structured output.

### S2: Marketplace listing discovery
- For each single SKU and each marketplace (Amazon.in, Flipkart, Nykaa, plus optionally Myntra, Purplle and Tira), run `/web/search/live` with query `"Dot & Key <title> <size>"` and `site=<marketplace>`.
- Take the top URLs, extract the canonical ID (ASIN, Flipkart `pid`, Nykaa product id) and **fuzzy-match** to the catalog with rapidfuzz on title, size and variant. Store the confidence and drop anything below the threshold.
- Cheaper alternative where it works: fetch one marketplace brand or search page such as `amazon.in/s?k=dot+and+key+<category>`. One page yields about 20 ASINs, compared with one search per SKU.

### S3: Listing fetch and parse
- Batch URLs 10 at a time through `/web/enrich/live`. Retry with `human_mode: true` on failure, which Nykaa needs.
- Write one parser per marketplace, using selectolax with JSON-LD and embedded-state extraction first:
  - **Amazon:** price, MRP, rating, rating count, BSR and category rank, "Customers say" summary and aspect chips, and the top ~8–10 reviews on the PDP.
  - **Flipkart:** price, MRP, rating, rating and review counts, rating histogram, and highlights.
  - **Nykaa:** the embedded preloaded-state JSON, if `human_mode` returns it.
- **LLM fallback:** when a selector breaks, send the cleaned text to a cheap OpenRouter model with a fixed JSON schema. This keeps the demo alive if a marketplace changes its HTML.
- Save every snapshot with a timestamp (`listing_snapshot`). This gives us price and rating history for the "monitoring" and "trends" claims.

### S4: Reviews
Ordered by value per effort:
1. **D&K Judge.me reviews** (first-party, high volume, no Crustdata credits).
2. **Amazon PDP top reviews** and the "Customers say" aspects. *Assumption to verify:* deep review pages (`/product-reviews/`) on Amazon.in require sign-in, so we rely on PDP reviews.
3. **Flipkart `/product-reviews/` pages**, which are server-rendered. Fetch 2–5 pages per SKU.
4. **Reddit threads** found through Crustdata search. Fetch `old.reddit.com/...json`.

Normalized `Review` record: source, product_ref, rating, title, body, date, verified, helpful_votes, skin_type (if stated). Deduplicate by hashing the body text.

### S5: Top-5 competitors per category
For each D&K category (e.g. Sunscreen):
1. **Candidates:** fetch the marketplace category search (`"sunscreen spf 50"`, `"vitamin c serum"`) on Amazon and Flipkart, take the first 2 pages and collect brand plus product.
2. **Seed list:** the brands we already know, used as validation (the brief says "a few known competitors"): Minimalist, The Derma Co, Deconstruct, Foxtale, Plum, Re'equil, Pilgrim, Aqualogica, Mamaearth, Lakmé, Neutrogena, Cetaphil. Add a Crustdata `ai` search ("top Indian D2C competitors to Dot & Key in sunscreen") to cross-check.
3. **Score** each candidate product with: `0.35·log(rating_count) + 0.25·rank_position + 0.2·price_band_overlap + 0.2·ingredient/claim_overlap`. Keep the top 5 per category, with **at most 1 product per brand**.
4. Run S3 and S4 on those competitor products so they get the same depth as D&K's.
5. **New launch detection:** run a Crustdata `news` search with `start_date` set to the last 90 days for each competitor brand, plus the marketplace "newest arrivals" sort.

### S6: Brand-level signals
- Run `/company/enrich` once per competitor brand domain (about 12–15 brands, about 30 credits). Store web traffic, follower growth, headcount and hiring growth, funding, news and SEO competitors.
- This becomes a "competitor momentum" panel, e.g. "Foxtale traffic +40% QoQ, hiring 12 growth roles".

### Output contract for Part 2
SQLite (or Postgres) tables: `product`, `listing`, `listing_snapshot`, `review`, `competitor_set(category, rank, product_ref, score, reasons)`, `brand_signal`, `news_item`, `crawl_log`. Plus a small FastAPI service with `GET /category/{c}/report-data` that returns everything for one category as a single JSON document. That JSON is the input to the sentiment, SWOT and content stages.

---

## 3. Credit and time budget (full run)

| Step | Calls | Credits |
|---|---|---|
| S2 discovery (about 65 SKUs × 3 marketplaces, minus shared brand-page shortcuts) | ~120 searches | ~120 |
| S3 D&K listing fetches | ~200 URLs | ~200 |
| S5 category searches (10 categories × 2 marketplaces × 2 pages) | 40 | 40 |
| S3 and S4 competitor listings and reviews (10 × 5 × 2 marketplaces × ~3 pages) | ~300 URLs | ~300 |
| S6 company enrich (15 brands) | 15 | ~30 |
| News, AI and social searches | ~60 | ~60 |
| **Total** | | **~750 credits** |

The 10 RPM limit on search and fetch is the bottleneck. One full crawl takes about 30–40 minutes. Fetch calls carry 10 URLs each, so search calls dominate. **Pre-crawl everything before the demo.** During the demo, refresh only one category live, which is about 15 calls and under 2 minutes. Cache all raw HTML on disk, keyed by URL hash.

---

## 4. Build order (hackathon day)

1. **Spike (30 min):** with the real key, call `/web/enrich/live` on one Amazon PDP, one Flipkart PDP, one Nykaa PDP (with and without `human_mode`) and one Flipkart reviews page. Also call `/web/search/live` with `site=amazon.in`. Record what comes back. **This decides the Nykaa path.**
2. Write the Crustdata client: auth, rate limiter (token bucket at 10 RPM per endpoint), 429 backoff, disk cache and credit logging.
3. S1 catalog loader and normalizer, plus Judge.me reviews. This gives demo-able data within about 1.5 hours.
4. Amazon and Flipkart parsers (S3), with the LLM fallback.
5. S5 competitor selection for **one hero category (Sunscreen: 12 SKUs, the most competitive market)**. Get it end to end first, then widen.
6. S6 brand signals and news.
7. JSON output endpoint for Part 2, then the background full crawl.

---

## 5. Risks and fallbacks

| Risk | Fallback |
|---|---|
| Nykaa blocks even `human_mode` | Drop Nykaa, or use a local Playwright fetch for a handful of hero SKUs |
| Amazon serves a CAPTCHA page through Crustdata | Detect it (`captcha` marker or empty `data-asin`), retry with `human_mode`, otherwise use Crustdata search snippets, which often contain the rating and price |
| Marketplace HTML changes or parsers break | Haiku extraction with a JSON schema on the cleaned text |
| Fuzzy matching picks the wrong variant or size | Match on size and SPF tokens as well as the title. Write a manual override CSV for the hero SKUs. |
| Credits run out | Cache aggressively, cover only the hero category, and use brand pages instead of per-SKU search |
| dotandkey.com 429 | Use only `products.json` and Judge.me, with 1 request per second |

---

## 6. Open questions for the team
- Which **hero category** do we demo? I recommend Sunscreen.
- Which Crustdata **plan tier** do we have? `company/enrich` fields like `web_traffic` and `social_posts` and the live social endpoints may be plan-gated, and `GET /account/endpoints` will tell us.
- Do we have Dot & Key's own **competitor list or brand guidelines** to validate against, which the brief lists as "what sharpens it"?
- Should Part 2 (sentiment and SWOT) read straight from SQLite, or only through the JSON endpoint?
