# Firecrawl Brand Discovery Spec

## Purpose
Use Firecrawl or an equivalent crawl/extract workflow to turn a brand website into structured brand input for Creator Breakout Kit.

## Crawl targets
Start with:
- homepage
- founder/about page
- top 3-5 product pages
- routines / how-to pages
- FAQ
- bundles / starter kit pages
- retailer / press pages if useful

## Extraction goals
Capture:
- what the brand sells
- hero products and price points
- founder or authority positioning
- product truth claims
- ingredients / feature language
- routine simplicity or complexity cues
- strongest buyer desires implied by the site
- strongest buyer objections implied by the site
- language worth preserving verbatim

## Required output fields
- `brand_name`
- `brand_url`
- `brand_summary`
- `hero_products`
- `price_points`
- `founder_positioning`
- `audience_hypothesis`
- `primary_desires`
- `primary_objections`
- `proof_points`
- `claim_risks`
- `source_coverage_notes`
- `verbatim_language`

## Rules
- Prefer extraction over interpretation when possible.
- Separate direct evidence from inference.
- Do not invent audience claims not supported by the brand.
- Flag weak source coverage clearly.

## Success condition
An operator should be able to read the extracted output and immediately understand:
- what makes the brand credible
- what buyers want
- what buyers are worried about
- what language the brief should preserve
