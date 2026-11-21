---
name: creator-breakout-kit
description: Run the full Creator Breakout Kit workflow when the user asks for creator strategy or direction — things like "what creator concepts should we test," "what content angles would you start with," or "what is breaking out in this category." Use when the user needs the creator angles, hooks, and concept directions most likely to break out before any money gets spent on sourcing or production — brand discovery, breakout pattern research, buyer-psychology mapping, a Creator Breakout Brief, internal research notes, and optional handoff copy for managed execution. Do not use for pure influencer recruiting, booked creator claims, availability checks, or raw outreach lists.
---

# Creator Breakout Kit (Orchestrator)

## Purpose
Find the creator angles, hooks, and concepts most likely to break out for a brand — before anyone pays to source or produce. Run the full Creator Breakout Kit pipeline end-to-end and produce:
- a client-ready **Creator Breakout Brief**
- internal research + decision notes
- optional sales handoff copy

This skill coordinates specialist modules. It does not replace them.

## Package contract
Use this skill from the `creator-breakout-kit` repo root. All paths below are relative to that root.

If this skill folder has been copied without `skills/`, `shared/`, and `scripts/`, stop and ask for the full package instead of improvising missing resources.

When this workflow names another skill, open that sibling `SKILL.md` file and follow it. Do not assume skill names are executable tools.

## Core positioning (must preserve)
- Find the creator angles, hooks, and concepts most likely to break out — before the brand pays to source or produce.
- Start from breakout patterns, buyer psychology, and brand truth, not follower count.
- The output is a test plan, not a brainstorm and not an influencer list.
- Strategy layer before sourcing, briefing, and managed execution.

## Guardrails
- Never imply creators are booked, sourced, or committed unless explicitly true.
- Treat creator names as reference comps only, never as a roster.
- Prioritize pattern fit over follower count.
- Treat audience sentiment as comment-derived directional signal, not statistically representative market research.
- Do not call a run client-ready until synthesis has produced the Creator Breakout Brief.

## Inputs
- `brand_name` (required)
- `brand_url` (required)
- `product_offer` (required)
- `price_point` (optional)
- `audience` (required)
- `primary_desire` (required)
- `primary_objections` (required, list)
- `platform_focus` (required)
- `category` (required)
- `creative_constraints` (optional)
- `objective` (default: `breakout-test-plan`)

## Outputs
- **Creator Breakout Brief** (`creator-breakout-brief.md`) — the client-ready artifact
- `internal_notes.md` — research, confidence, evidence quality, caveats, next-step logic
- `sales_handoff.md` (optional) — bridge into sourcing, briefing, managed execution
- `breakout-kit.json` — structured output following `shared/schemas/breakout-kit.schema.json`

## Workflow
1. Validate required inputs and choose the run mode from `README.md` (`quick-pass`, `brand-pass`, `pending-data`, `outlier-pass`, or `deep-pass`).
2. Open `skills/brand-snapshot/SKILL.md` and produce the brand snapshot contract.
3. Open `skills/breakout-pattern-research/SKILL.md` and produce the breakout pattern contract.
4. Open `skills/creator-archetype-mapper/SKILL.md` and map archetypes to the strongest patterns.
5. Open `skills/creator-concept-generator/SKILL.md` and produce the concept slate with hooks + filming beats.
6. Open `skills/creator-kit-formatter/SKILL.md` and split the structured kit into the Creator Breakout Brief and internal notes.
7. Optionally open `skills/sales-handoff/SKILL.md` to produce concise CTA/follow-up copy.

For connector-backed runs, prefer the deterministic repo scripts over ad hoc agent research:

```bash
bash scripts/preflight.sh
python3 scripts/create_base_breakout_run.py --brand-name "$BRAND_NAME" --brand-url "$BRAND_URL" --product-offer "$PRODUCT_OFFER" --audience "$AUDIENCE" --primary-desire "$PRIMARY_DESIRE" --primary-objections "$PRIMARY_OBJECTIONS" --platform-focus "$PLATFORM_FOCUS" --run-dir "$RUN_DIR"
bash scripts/run_creator_breakout_research.sh --brand-name "$BRAND_NAME" --brand-url "$BRAND_URL" --niche "$CATEGORY" --keywords "$KEYWORDS" --out-dir "$RESEARCH_DIR"
python3 scripts/enrich_breakout_run.py --run-dir "$RUN_DIR" --research-dir "$RESEARCH_DIR" --overwrite
python3 scripts/synthesize_full_kit.py --run-dir "$RUN_DIR"
```

Optionally run `python3 skills/breakout-pattern-research/scripts/virlo_tracking_intelligence.py --research-dir "$RESEARCH_DIR" --limit 3 --track videos --scrape-cadence weekly` after Virlo outlier research and before enrichment when the brief needs comment-derived buyer language. This can start paid Virlo Tracking cycles, so use it intentionally; rerun the adapter later if reports are still pending.

Run `python3 skills/breakout-pattern-research/scripts/video_intelligence.py --run-dir "$RUN_DIR" --limit 3 --max-video-mb 20` after enrichment and before synthesis only when `SCRAPECREATORS_API_KEY` and `OPENROUTER_API_KEY` are configured; otherwise synthesis will keep the metadata-only evidence limitation.

Treat `run_creator_breakout_research.sh` and `enrich_breakout_run.py` as connector/research stages only. Do not call a run client-ready until `synthesize_full_kit.py` has materialized `brand-snapshot.json`, `breakout-pattern-research.json`, `creator-archetype-map.json`, `concept-slate.json`, and `skill-run-manifest.json`.

For a quick-pass base run without live connectors, start with:

```bash
python3 scripts/create_base_breakout_run.py --brand-name "$BRAND_NAME" --brand-url "$BRAND_URL" --product-offer "$PRODUCT_OFFER" --audience "$AUDIENCE" --primary-desire "$PRIMARY_DESIRE" --primary-objections "$PRIMARY_OBJECTIONS" --platform-focus "$PLATFORM_FOCUS" --run-dir "$RUN_DIR"
```

## Quality bar
- Specific to the brand category and buyer language.
- Pattern-backed and outlier-ratio aware.
- Concepts map to objections/desires, not generic UGC advice.
- First-test recommendation is concrete and production-feasible.

## Failure handling
If inputs are thin:
1. Return a gap list.
2. Ask for minimum missing data.
3. Produce a constrained draft with confidence flags.

## Example invocation
See: `shared/examples/example-invocation.md`

## Style contract
Apply: `shared/templates/style-profile.md` to all generated outputs.
