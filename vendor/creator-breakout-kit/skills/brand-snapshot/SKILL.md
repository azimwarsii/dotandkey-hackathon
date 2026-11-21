---
name: brand-snapshot
description: Convert brand inputs, landing pages, product context, buyer desires, objections, and source material into a decision-ready Creator Breakout Kit brand snapshot. Use inside the Creator Breakout Kit workflow when buyer psychology, product truth, brand language, source coverage, and confidence notes are needed before pattern research or concept generation.
---

# Brand Snapshot

## Purpose
Convert raw brand inputs into a decision-ready snapshot for concepting.

## Package contract
Use from the `creator-breakout-kit` repo root. Paths are relative to that root.

## Primary data source
- Preferred: Firecrawl-style brand discovery across homepage, product pages, founder/about pages, FAQ, bundles, routines, and retailer/supporting pages.
- Fallback: manual site fetch + search when crawl infrastructure is unavailable.

## Inputs
- Brand website/LP context
- Product and offer
- Audience details
- Price point (if known)
- Objections, desires, constraints

## Outputs
- `brand_summary` (what they sell, for whom, why now)
- `buyer_psychology_map`
- `top_3_objections`
- `top_2_desire_states`
- `platform_notes`
- `brand_discovery_confidence`
- `source_coverage_notes`

## Workflow
1. For Firecrawl-backed runs, run `python3 skills/brand-snapshot/scripts/firecrawl_brand_discovery.py --brand-name "$BRAND_NAME" --brand-url "$BRAND_URL" --out-dir "$RESEARCH_DIR"`.
2. If Firecrawl is unavailable, use manual site fetch/search and label the run `quick-pass` or `brand-pass` as appropriate.
3. Read `skills/brand-snapshot/references/firecrawl-brand-discovery.md` before interpreting brand discovery outputs.
4. Distill what the product does and why buyer cares.
5. Identify emotional and identity drivers.
6. Rank objections by likely conversion drag.
7. Translate into content-usable language (hooks, proof, story).
8. Flag what is inferred versus directly evidenced from brand materials.

## Prompting guidance
- Use niche language from the category.
- Avoid broad statements like "authentic UGC works."
- Prefer concrete buyer tensions and outcome language.
- Pull exact phrases worth reusing from brand pages when they clarify positioning.

## Quality bar
- Could drive a creator concept pass without follow-up questions about the brand.
- Objections are specific and behaviorally realistic.
- Desire states are testable in hook language.
- Confidence and source coverage are explicit.
