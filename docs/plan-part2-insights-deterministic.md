# Part 2 Plan: Deterministic Insights (SWOT, Gaps, Trends, Launches)

**Principle:** rules and statistics do the reasoning, and AI is optional polish. Every insight is a **metric plus a threshold plus evidence**: numbers, sample size and 2–3 quoted reviews. The same data always produces the same output, and every claim is traceable for the judges.

Input: the tables from Part 1 (`product`, `listing_snapshot`, `review`, `competitor_set`, `brand_signal`, `news_item`).

---

## 1. Foundation: aspect tagging without an LLM

Everything below depends on knowing *what* each review talks about and *whether it is positive or negative*.

**Aspect lexicon** (`lexicons/aspects.yaml`, about 20 skincare aspects, hand-written and frozen):

```yaml
white_cast:
  neg: ["white cast", "leaves white", "ashy", "whitish", "white layer"]
  pos: ["no white cast", "zero white cast", "doesn't leave white", "blends in"]
greasy_sticky:
  neg: ["greasy", "sticky", "oily", "heavy", "chipchipa"]
  pos: ["non greasy", "non-sticky", "lightweight", "matte finish"]
breakouts:
  neg: ["breakout", "broke me out", "pimples", "acne", "clogged", "dane"]
  pos: ["no breakouts", "didn't break me out", "acne safe"]
irritation: ...      # burning, stinging, rash, redness, itchy
fragrance: ...       # smell, perfume, scent (both directions)
hydration: ...       # dry, tight, moisturised, plump
glow_results: ...    # glow, brightening, tan removal, pigmentation faded
texture: ...         # gel, creamy, watery, pilling
packaging: ...       # pump broke, leaked, tube, cap
value_price: ...     # overpriced, worth it, value for money, small quantity
authenticity: ...    # fake, duplicate, expired, seal broken (marketplace-specific)
spf_protection: ...  # tanned anyway, sunburn, protects
longevity: ...       # reapply, wears off, lasts all day
under_makeup: ...    # pills under makeup, good base
```

**Tagger, run on each sentence:**
1. Split sentences (spaCy `en_core_web_sm`, rule-based, deterministic).
2. Match `pos` phrases first, because they often contain the `neg` phrase ("no white cast"), then `neg` phrases.
3. Handle negation: a negator (`not, no, never, without, zero, doesn't, isn't`) within 3 tokens before a `neg` cue flips it to positive.
4. Fallback polarity when an aspect is matched only by a neutral word ("the smell…"): use the review's star rating (≥4 pos, ≤2 neg, 3 neutral).
5. **Optional and still free:** a local sentence-sentiment model (e.g. a distilled SST-2 or multilingual BERT on CPU, with fixed weights, so it stays deterministic) for sentences the lexicon can't decide.

**Validation:** hand-label about 150 sentences and report precision per aspect. Drop or fix any aspect below 0.7. This table goes on a demo slide ("our tagger is 84% precise on white cast").

*One-time AI use (optional):* give Claude a sample of 500 reviews **once** to suggest extra synonyms. A human reviews them and freezes them into the YAML. After that there are zero runtime AI calls.

---

## 2. Core metrics (computed per product, brand and category)

| Metric | Formula | Why |
|---|---|---|
| Bayesian rating | `(C·m + Σr) / (C + n)`, with m = category mean rating and C = 50 | Stops a 5.0 from 12 reviews beating a 4.3 from 40k |
| Aspect mention rate | mentions / reviews | What customers care about (share of voice) |
| Net sentiment score (NSS) | `(pos − neg) / (pos + neg)` per aspect | Direction on each aspect |
| Confidence | Wilson interval on pos share, requiring n ≥ 30 mentions | No conclusions from tiny samples |
| Complaint lift | `P(aspect │ 1–2★) / P(aspect │ all reviews)` | Which aspects *drive* bad ratings |
| Review velocity | Δ`rating_count` between snapshots / days, plus review dates per month | Demand and sales proxy |
| Price index | price per ml or g ÷ category median price per ml or g | Positioning (premium, parity or value) |
| Discount depth | `1 − price/MRP` over time | Promo pressure from competitors |

All of this is pandas group-bys with no model involved.

---

## 3. SWOT: rule table

Each rule emits a row of `{quadrant, title, metric_values, n, evidence_quotes}`. A **template** renders the sentence, e.g. *"White cast: 18% of D&K sunscreen reviews mention it, with net sentiment −0.42 against a top-5 competitor median of +0.10 (n=312)."*

| Quadrant | Rule (D&K product or category vs its top-5 set) |
|---|---|
| **Strength** | Aspect NSS ≥ peer median + 0.15, with the Wilson lower bound above the peer median and n ≥ 30 |
| | Bayesian rating in the top 2 of the 6 (D&K plus 5) |
| | Price index ≤ 0.9 with rating ≥ peer median (value leader) |
| | Fastest review velocity in the set (momentum) |
| **Weakness** | Aspect NSS ≤ peer median − 0.15 (significant) |
| | Aspect with complaint lift ≥ 2 and mention rate ≥ 5% |
| | Rating on one marketplace ≥ 0.3★ below the same SKU elsewhere (channel or authenticity problem) |
| **Opportunity** | Aspect where **≥ 4 of 5 competitors** have negative NSS (category-wide pain, see Gaps) |
| | Competitor weakness on an aspect where D&K is a strength (attack messaging) |
| | Trending ingredient or claim (§5) that D&K lacks in this category |
| | Attribute whitespace cell (§4) |
| **Threat** | Competitor launch in this category within 90 days (§6) |
| | Competitor with a higher rating and price index ≤ D&K's (better and cheaper) |
| | Competitor brand momentum from Crustdata: traffic or follower growth QoQ ≥ 20%, or a hiring spike |
| | Competitor discount depth up ≥ 10 points in 30 days (price war) |

Rank the rows inside each quadrant by `effect size × log(n)` and show the top 3–5.

---

## 4. Market gaps: three deterministic methods

1. **Attribute whitespace matrix.**
   - Extract attributes for every product in the category, D&K and competitors. Both come from Shopify feeds (tags, title and `body_html`), parsed with regex and dictionaries:
     - SPF and PA
     - format (gel, cream, stick, spray, tinted, serum)
     - skin type
     - hero ingredients
     - price band
     - size
   - Build a pivot of category × attribute combination, counting products and summing review volume.
   - **Gap** = a combination with few products (≤ 1) but strong demand nearby: high review volume in neighbouring cells, or matching wish-phrases (method 3).
   - Example output: *"Tinted SPF 50 for oily skin under ₹500: only 1 product across the top-6 brands."*
2. **Category-wide pain:** an aspect with negative NSS across ≥ 4 of the 5 competitors and D&K. Nobody solves it yet, which makes it a product opportunity.
3. **Unmet-need phrase mining:**
   - Regex over reviews and Reddit for `wish (it|they)…`, `if only…`, `would be (great|perfect) if…`, `please (launch|make|bring)…`, `looking for a…`, `should come in…`, `needs (a|an|more)…`.
   - Capture the clause after the trigger, normalize it with the aspect and attribute dictionaries, and count.
   - Top clusters become "emerging customer needs".
   - Clustering of leftover free text uses a local MiniLM embedding plus KMeans with a fixed seed. This is free and deterministic.

---

## 5. Emerging trends: growth of terms over time

No waiting for multiple crawls is needed. **Review dates and Shopify `created_at` already give us years of history.**

- **Term dictionary:** about 120 ingredients and claims (niacinamide, ceramide, cica or centella, tranexamic, azelaic, peptide, retinal, bakuchiol, PDRN, rice water, mugwort, ectoin, mineral or hybrid filter, "skin tint", "barrier repair", "fragrance-free", and so on).
- **Signal A, launches:** the share of new products across all competitor catalogs that contain each term, comparing the last 6 months with the prior 12 months.
- **Signal B, reviews:** the term's mention rate in the last 90 days compared with the prior 270 days.
- **Signal C, optional:** a Crustdata `news` search where `metadata.total_results` per term per quarter is the count.
- **Score:** `growth = (recent_rate + α) / (base_rate + α)` with α for smoothing and minimum support ≥ 15. A term is **trending** when growth ≥ 1.5 on at least 2 of the signals.

---

## 6. New competitor launches: diff the catalogs (zero AI, almost zero Crustdata credits)

**Verified on 21 Nov:** all of these expose a public Shopify `/products.json` and published products in the last few weeks.
- Minimalist
- Foxtale
- The Derma Co
- Deconstruct
- Plum
- Re'equil
- Pilgrim
- Aqualogica
- Mamaearth

**Steps:**
- Snapshot each competitor's full catalog daily and store `product_id`, `created_at`, `published_at`, price and tags.
- A **launch** is a product ID not seen before, or one with `created_at` in the last 90 days on the first run. Bundles, combos and free items are excluded by `product_type` and title regex. `published_at` alone is not trusted, because brands republish existing products.
- Map each launch to a D&K category with the same category and attribute parser. A launch inside a D&K category becomes a Threat row, and the trend counter (§5A) gets its terms.
- **Cross-checks:**
  - a new ASIN appearing in the Amazon category search between crawls
  - the earliest review date on the PDP
  - a Crustdata `news` search matching `launch|introduces|unveils|new` together with the brand name
- The same snapshots also give **competitor price changes and new discounts** for free.

---

## 7. Sales-opportunity forecast (keep it modest)

- **Demand proxy:** monthly review counts per product and category, using review dates plus Δ`rating_count` between snapshots. Reviews are a roughly stable fraction of orders, so this tracks *relative* demand. Label it as an index, not units.
- **Model:** Holt-Winters or a linear trend (statsmodels, fixed parameters), forecasting 3–6 months per category.
- **Opportunity score per category:**
  - formula: `forecast_growth × (1 − D&K share of review volume in the top-6) × gap_count`
  - meaning: a growing category where D&K is under-represented and gaps exist

---

## 8. Recommendations: lookup tables, not generation

| Trigger | Output template |
|---|---|
| Weakness `white_cast` | Improve: switch to a hybrid or tinted filter system, and position it as an "invisible finish" variant |
| Weakness `greasy_sticky` | Improve: a lighter gel or fluid texture, and lead with "matte finish" claims |
| Weakness `packaging` | Improve: a pump or airless pack, and treat this as an ops issue rather than formula |
| Weakness `authenticity` (marketplace-specific) | GTM: brand-store-only listings, seller audit, and "buy from official store" messaging |
| Gap cell (attribute combination) | New product: "<format> <claim> for <skin type> at ₹<band>" |
| Trending ingredient missing at D&K | New product or line extension with that ingredient in the strongest D&K category |
| D&K strength vs competitor weakness | Messaging: comparison-led claims ("no white cast, unlike most SPF 50s") |
| Price index > 1.2 with rating ≤ peers | Pricing: smaller trial size or a value pack |
| Channel rating gap | Channel GTM: fix listing content and reviews on the weaker marketplace |

About 30 rows written by hand. Each recommendation links back to the SWOT and gap rows that triggered it, so you can trace it in the demo.

---

## 9. Where AI is still used (bounded and optional)

| Use | Calls | Needed? |
|---|---|---|
| Lexicon bootstrap (one time) | 1–3 | Optional |
| Turning the templated SWOT and gaps into a short executive narrative | 1 per category (about 10 in total) | Optional; templates already read fine |
| Content generation (ads, scripts, A+ listings) | Part 3 | Yes, but it consumes these deterministic facts as its brief |

The pipeline produces a complete report with AI switched off.

---

## 10. Stack and build order

**Stack:**
- pandas and numpy
- spaCy `en_core_web_sm`
- rapidfuzz
- scipy (Wilson interval and z-tests)
- statsmodels (Holt-Winters)
- PyYAML lexicons
- optionally sentence-transformers `all-MiniLM-L6-v2` and scikit-learn KMeans (seeded)

**Build order:**
1. Competitor Shopify catalog snapshotter plus launch diff. This takes about an hour and needs no scraping.
2. Aspect lexicon and tagger for Sunscreen, plus the 150-sentence validation.
3. The metrics table, then SWOT rules with evidence templates.
4. Attribute parser, then the whitespace matrix and unmet-need regex.
5. Trend growth scores, then the forecast.
6. The recommendation lookup, then the JSON for the UI and for Part 3.
