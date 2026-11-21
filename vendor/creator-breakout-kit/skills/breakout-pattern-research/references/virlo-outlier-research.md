# Virlo Outlier Research Spec

## Purpose
Use Virlo or an equivalent post-level performance source to identify breakout content patterns based on performance outliers, not follower count.

## Research goal
Find repeatable content structures in the category that materially outperform creator baselines.

## Search inputs
- category / niche
- platform focus
- optional subtopics
- optional brand-fit notes

## Required source analysis per candidate post
Capture:
- `post_url`
- `creator_handle`
- `platform`
- `views`
- `engagement_signals`
- `creator_baseline_view_median`
- `outlier_ratio`
- `hook_summary`
- `story_structure`
- `format_notes`
- `production_notes`
- `brand_fit_notes`

## Pattern synthesis rules
- Do not promote one-off anomalies with no repeatability.
- Look for repeated hook structures across multiple creators/posts.
- Score patterns on:
  - outlier strength
  - repeatability
  - brand fit
  - production feasibility
- Keep evidence references attached to each pattern.

## Required output fields
- `research_mode_used`
- `source_posts`
- `breakout_patterns`
- `hook_styles`
- `pattern_confidence_scores`
- `evidence_summary`

## Claim safety
- If no real Virlo pull happened, mark the run `quick-pass`.
- Do not describe manual synthesis as outlier-backed research.
- Shareable brief outputs should only use strong evidence language when source coverage is real.

## Success condition
An operator should be able to point to the actual source posts and explain why a pattern is worth testing first.
