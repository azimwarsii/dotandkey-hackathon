---
name: breakout-pattern-research
description: Research repeatable breakout content patterns for a Creator Breakout Kit using post-level outlier behavior, creator baselines, platform focus, and category fit. Use when the workflow needs hook styles, source posts, outlier evidence, confidence scores, or an honest quick-pass/brand-pass/pending-data/outlier-pass label before creator archetype mapping and concept generation.
---

# Breakout Pattern Research

## Purpose
Find repeatable breakout content patterns using outlier behavior, not creator popularity.

## Package contract
Use from the `creator-breakout-kit` repo root. Paths are relative to that root.

## Primary data source
- Preferred: Virlo or equivalent post-level performance dataset with creator baselines.
- Fallback: manual social review, but label output as constrained and lower confidence.

## Evidence limitation
Treat Virlo as metadata-only unless the adapter output explicitly includes transcripts, OCR, frame-level analysis, human-reviewed video notes, or `video-intelligence.json`. Captions, descriptions, hashtags, topics, thumbnails, and outlier ratios can support pattern hypotheses, but they do not prove what visually happens in a video.

When `SCRAPECREATORS_API_KEY` and `OPENROUTER_API_KEY` are configured, run `python3 skills/breakout-pattern-research/scripts/video_intelligence.py --run-dir "$RUN_DIR" --limit 3 --max-video-mb 20` after enrichment and before full-kit synthesis. This uses ScrapeCreators plus Gemini to add content DNA for promoted TikTok/Reels posts. It sends video assets inline when they fit under the size cap, otherwise it falls back to metadata/transcript/cover-image inputs.

When audience language would materially improve the brief and `VIRLO_API_KEY` is configured, optionally run `python3 skills/breakout-pattern-research/scripts/virlo_tracking_intelligence.py --research-dir "$RESEARCH_DIR" --limit 3 --track videos --scrape-cadence weekly`. Treat `virlo-audience-signals.json` as comment-derived directional signal, not statistically representative market research. The first run may queue tracking only; rerun the adapter later when Virlo reports are ready.

## Inputs
- Category / niche
- Platform focus
- Optional data source notes (Virlo/ScrapeCreators/manual)
- Optional Virlo Tracking audience signals
- Optional brand snapshot for tighter scoring

## Outputs
- `breakout_patterns` (3-5)
- `hook_styles` (3-5)
- `outlier_evidence_notes`
- `pattern_confidence_scores`
- `source_posts`
- `research_mode_used`
- optional `audience_signals`

## Workflow
1. For Virlo-backed runs, run `python3 skills/breakout-pattern-research/scripts/virlo_outlier_research.py --brand-name "$BRAND_NAME" --niche "$CATEGORY" --keywords "$KEYWORDS" --out-dir "$RESEARCH_DIR"`.
2. If Virlo is unavailable or pending, label the run `quick-pass`, `brand-pass`, or `pending-data`; do not call the output outlier-backed.
3. Read `skills/breakout-pattern-research/references/virlo-outlier-research.md` before interpreting Virlo or manual source outputs.
4. Gather niche examples with strong breakout behavior.
5. Compare each example against creator baseline performance when available.
6. Extract repeated structures (hook, tension, reveal, CTA shape).
7. Remove one-off anomalies with weak replication signal.
8. Rank patterns by repeatability + brand fit.
9. Store representative source posts and one-line evidence notes.
10. Separate what the metadata says from what the strategy borrows. Do not describe visual beats unless a human or video-analysis tool actually reviewed the video.
11. If `video-intelligence.json` exists, use its `content_dna` fields for hook structure, story beats, visual format, key visuals, audio, and reusable mechanics; preserve its confidence/limitation language.
12. If `virlo-audience-signals.json` exists, use ready audience sentiment for hook language and objection clues; keep queued or pending reports labeled as pending.

## Pattern scoring rubric
- `outlier_ratio`: performance vs creator baseline.
- `repeatability`: seen across multiple creators/posts.
- `brand_fit`: can adapt to product truthfully.
- `production_feasibility`: realistic to shoot quickly.

Score each 1-5 and include one-line rationale.

## Research modes
### 1. Quick pass
- no live Virlo pull
- uses known category heuristics and manual review
- acceptable for internal drafting, not strong enough for “data-backed” claims

### 2. Outlier pass
- live Virlo-backed source post review
- includes outlier ratios, repeated structures, and evidence log
- recommended default for serious client work

### 3. Deep pass
- outlier pass plus creator-comp mapping and more source coverage
- optional Virlo Tracking audience sentiment for selected source videos or creators
- use for paid strategy or higher-stakes pitches

## Quality bar
- Evidence mentions why pattern is an outlier.
- Recommendations avoid follower-count bias.
- Output is usable by concept generation without extra research.
- Shareable brief output should not overstate evidence quality when run in quick-pass mode.
