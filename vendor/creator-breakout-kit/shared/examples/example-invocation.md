# Example Invocation Flow

## Minimal input payload

```json
{
  "brand_name": "Example Hydration",
  "brand_url": "https://example.com",
  "product_offer": "electrolyte mix for active professionals",
  "audience": "25-40 professionals balancing work and training",
  "primary_desire": "sustained energy without sugary drinks",
  "primary_objections": [
    "skeptical of supplement claims",
    "concerned about taste",
    "does not want a complicated routine"
  ],
  "platform_focus": "TikTok",
  "category": "hydration",
  "research_mode": "outlier-pass"
}
```

## Recommended orchestrator run sequence
1. `creator-breakout-kit` receives input.
2. `brand-snapshot` runs with Firecrawl-style brand discovery when available.
3. `breakout-pattern-research` runs in the selected research mode.
4. `creator-archetype-mapper` maps creator types from pattern fit.
5. `creator-concept-generator` builds the concept slate.
6. `creator-kit-formatter` creates client and internal outputs.
7. Optionally `sales-handoff` creates concise send language.

## Research mode guidance
- `quick-pass` = manual brand/site review + pattern synthesis
- `outlier-pass` = real brand discovery + real Virlo-backed outlier review
- `deep-pass` = outlier pass plus broader creator-comp depth

## Output package
- `creator-breakout-brief.md`
- `internal_notes.md`
- `breakout-kit.json` (schema-compliant)
- `sales_handoff.md` (optional)
