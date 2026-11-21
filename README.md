# Dot & Key market intelligence

The [Part 1 collector](docs/plan-part1-market-intel.md) stores catalog, marketplace and review observations in SQLite. The [Part 2 pipeline](docs/plan-part2-insights-deterministic.md) turns those observations into evidence-linked SWOT findings, market gaps, launch signals, three-month demand projections and recommendations. Both APIs work offline against the included databases. Start with the [Sunscreen insights](data/sunscreen-insights.json) or the [ten-category opportunity ranking](data/part2-opportunities.json).

## Content Studio (Part 3)

The [Content Studio](studio-web) connects the per-product brief to reference research, concepts, scripts, storyboard frames, video exports, ads, marketplace listings and test results. The included [Watermelon Sunscreen campaign](data/studio/runs/watermelon-demo) opens with saved artifacts. [Setup, demo walkthrough and refresh commands](docs/content-studio.md)

## Included crawl

The 21 November 2026 dataset contains 66 single Dot & Key products, 55 linked combos and 50 ranked competitors across ten categories. All 66 singles have a matched marketplace listing and a timestamped observation. There are 248 listings across Amazon India (74), Flipkart (85) and Nykaa (89), and 257 marketplace observations. The 6,133 deduplicated review records comprise 3,606 Judge.me reviews, 1,629 Flipkart reviews, 582 Amazon reviews, 306 Nykaa reviews and 10 indexed Reddit excerpts. Nykaa covers 59 of 66 Dot & Key singles and 30 of 50 selected peers.

The database includes 33 verified Crustdata company records, 160 dated company-news articles and 11 dated public storefront signals. Twenty-two records identify the brand directly. The other 11 identify a parent, brand family or US profile and are excluded from Indian brand momentum comparisons. Independent source citations named 16 of the 50 selected marketplace competitors across seven categories.

Crustdata retrieved usable Nykaa data in both fetch modes and ten variant-labelled reviews from the Flipkart review page. Its Amazon fetch returned a challenge page, so the Amazon figures come from the public crawl. The ten Reddit excerpts came from indexed Reddit posts or comments and retain their permalinks and date precision. See the [authenticated probe](data/crustdata-spike.json).

## Read the data

From the repository root, using Python 3.9 or later:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m market_intel report Sunscreen --output data/sunscreen.json
.venv/bin/uvicorn market_intel.api:app
```

Open [the Sunscreen JSON report](http://127.0.0.1:8000/category/Sunscreen/report-data) or [the interactive API documentation](http://127.0.0.1:8000/docs). Category names are case-insensitive. Use URL encoding for names with spaces, such as `/category/Face%20Wash/report-data`. An unknown category returns 404.

One report contains `products`, `listings`, `listing_snapshots`, `reviews`, `competitor_set`, `brand_signals` and `news_items`. Join records by `product_ref` and listings by `(product_ref, market, external_id)`. Snapshot timestamps record when the source was observed. Marketplace reviews use ISO dates when the source gives a calendar date. A relative date such as “six months ago” stays in `date_text` alongside the observation timestamp. A review can include its original marketplace shade or size when a product page groups variants. Empty collections and missing values indicate gaps in the observed data. The `crawl_log` table records upstream responses, errors and reported credit usage. The catalog retains all Shopify variants. Marketplace discovery compares the primary available variant and supports SKU-specific overrides for differences between store and marketplace labels.

## Read the insights

```sh
.venv/bin/python -m market_intel insights Sunscreen --as-of 2026-11-21 --output data/sunscreen-insights.json
.venv/bin/python -m market_intel opportunities --as-of 2026-11-21 --output data/part2-opportunities.json
```

With the API running, open the [Sunscreen insights endpoint](http://127.0.0.1:8000/category/Sunscreen/insights) or the [category ranking endpoint](http://127.0.0.1:8000/insights/opportunities). Both accept an optional `as_of=YYYY-MM-DD`. By default a category uses its latest stored listing or competitor catalog observation. Historical windows use the stored Part 1 product metadata and peer selection. The reports expose the observations and denominators behind each comparison.

| Report field | What it contains |
|---|---|
| `metrics` | Product, brand and category ratings, aspect mentions, complaint lift, Wilson intervals, review activity, comparable unit prices and observed discounts |
| `swot` | Up to five findings per quadrant, ranked by effect size × log(sample size), with thresholds and review quotes or source listings |
| `gaps` | Attribute combinations with sparse supply and nearby demand, category-wide complaints, and recurring requests with their original wording |
| `trends` | Per-term growth across dated catalog creations and reviews, qualifying terms, recent launch candidates, and observed price changes |
| `forecast` | A three-month relative review-activity index, monthly observations, model assumptions and opportunity score factors |
| `recommendations` | Rule-based actions whose `trigger_ids` identify the underlying claims or gaps |

The forecast fits observed months only. It requires six months of coverage, observations in each of the latest three complete months, and at least 30 observations. A score also requires review-volume evidence for Dot & Key and all five selected competitors. A missing score includes the reason. The underlying marketplace review sample and product coverage vary by brand. Nykaa can attach a parent rating to multiple sizes or shades. The SKU analysis retains each observed child price and excludes explicitly pooled parent ratings and counts.

On 21 November, six categories met the projection requirements. Lip Balm ranked first on the opportunity score (0.695). None of the 124 tracked terms had sufficient growth on both catalog and review evidence.

The frozen aspect evaluation used 150 source-linked sentences. Six of 18 aspects passed the release gate of ≥70% exact aspect-and-polarity precision with at least five predictions. Sentiment comparisons also require 30 directional mentions. The annotations were model-reviewed and await independent human review. See the [precision table and reproduction steps](validation/README.md) and [editable demo slide](validation/aspect-validation.pptx).

The supplied exports use pinned local MiniLM weights and seeded clustering for uncategorized wish clauses. The lightweight installation uses deterministic token overlap if the local model is unavailable. To reproduce the semantic run from a fresh checkout, follow the [local model setup](docs/local-minilm.md) before exporting.

## Daily competitor catalog

The first observation on 21 November 2026 covers 3,102 Shopify product IDs across nine stores and 564 Amazon search observations across ten categories. Products created within 90 days qualify as baseline launch candidates. Later snapshots compare product identities, Amazon results and the same price variants across dates. Each candidate identifies its evidence and any independent corroboration. The baseline identified 59 recent catalog launch candidates. Price changes and new Amazon search appearances require a later observation.

```sh
.venv/bin/python -m market_intel catalog-snapshot
```

The command safely resumes partial days and stores each brand’s complete daily catalog in `data/competitor-catalogs.sqlite3`. Set `COMPETITOR_CATALOG_DB` or the global `--catalog-db` option to change its location. For a checkout at `/srv/dotandkey-hackathon`, this cron entry schedules collection at 03:15 in the host’s time zone.

```cron
15 3 * * * cd /srv/dotandkey-hackathon && .venv/bin/python -m market_intel catalog-snapshot
```

## Refresh collection

```sh
# Public catalog and up to two Judge.me pages per single product
.venv/bin/python -m market_intel crawl --stage first-party

# Collect a deeper first-party sample, including reviews buried in shared widgets
.venv/bin/python -m market_intel crawl --stage first-party --judgeme-pages 10

# Refresh one category end to end, including its competitors and reviews
.venv/bin/python -m market_intel crawl --category Sunscreen --refresh

# Run every category, prioritizing Sunscreen
.venv/bin/python -m market_intel crawl
```

Public mode uses Shopify and Judge.me, direct marketplace pages and public news RSS. For supported competitor storefronts, brand signals include dated Shopify product publications from a sample of up to 50 products. Crustdata supplies company traffic, hiring, funding and follower metrics when the key has access. Amazon and Flipkart coverage depends on the search results, matching size or variant, and the fields visible on the listing. Nykaa collection uses Crustdata. An arrival in a marketplace's newest-sort results has an unknown launch date unless a dated news source also reports the launch.

Copy `.env.example` to `.env` to configure the providers. `CRUSTDATA_API_KEY` enables marketplace and social search, batched page retrieval, browser-like retrieval via the provider, news, AI competitor checks and company enrichment. Provider requests consume credits. Set `OPENROUTER_API_KEY` to extract missing catalog and listing fields using `anthropic/claude-haiku-5.5`. Override the model with `OPENROUTER_MODEL`. Catalog additions record a matching source excerpt and URL. Direct Anthropic access remains available with `ANTHROPIC_API_KEY` when OpenRouter is unconfigured. Part 2 report generation runs locally. Credentials are optional for the included database and public crawl.

```sh
# With a Crustdata key, record account permissions and the search and fetch spike
.venv/bin/python -m market_intel spike --output data/crustdata-spike.json

# Backfill exact Nykaa child listings, prices, parent-rating scope and attributable reviews
.venv/bin/python -m market_intel.nykaa

# Reuse the stored catalog and refresh marketplace coverage only
.venv/bin/python -m market_intel crawl --stage market --category Sunscreen
```

The [public probe](data/public-spike.json) records direct HTTP results for the same representative pages. Reproduce it with `python -m market_intel spike --public --output data/public-spike.json`.

Raw responses are cached under `data/cache` for 24 hours. Use `--refresh` to fetch fresh observations. `--judgeme-pages`, `--review-pages` (0–5 for Flipkart) and `--reddit-threads` control collection depth. Use `--overrides path/to/listings.csv` for verified product mappings with columns `product_ref,market,url`. The packaged overrides are in [listing_overrides.csv](market_intel/listing_overrides.csv). `MARKET_INTEL_DB` sets the database path for both the service and CLI. The CLI also accepts `--db` and `--cache` before the subcommand.

## Competitor selection

Categories cover Sunscreen, Moisturiser, Serum, Face Wash, Lip Balm, Toner, Mask, Eye, Body and Hair. The collector searches two marketplace result pages per category, excludes bundles and Dot & Key, and scores observed products. The score weights log rating count normalized by the category maximum (35%), discounted search position (25%), overlap with the observed Dot & Key price range (20%) and ingredient or claim overlap with the closest Dot & Key product (20%). Missing dimensions contribute zero. It retains at most five distinct brands. The report includes source URLs, raw values, score components and validation evidence. Company enrichment stores the sections returned for a matched brand domain. A repeated brand is enriched once per run.

## Verify

```sh
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q
```

The tests cover collection, snapshot history, frozen tagger precision, metrics, gaps, trend and SWOT thresholds, demand projections, recommendation traceability, API responses and CLI exports.
