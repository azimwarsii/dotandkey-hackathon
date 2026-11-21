---
name: creator-concept-generator
description: Generate a Creator Breakout Kit concept slate from brand snapshot, breakout pattern evidence, buyer objections/desires, platform focus, and creator archetype fit. Use when the workflow needs 3 default creator/content concepts, hooks, filming beats, breakout rationales, and a concrete first-test recommendation.
---

# Creator Concept Generator

## Purpose
Generate concept slate from pattern evidence, objections, and archetype fit.

## Package contract
Use from the `creator-breakout-kit` repo root. Paths are relative to that root.

## Inputs
- `brand_snapshot`
- `breakout_patterns`
- `archetypes`
- `objections_and_desires`
- `platform_focus`

## Outputs
- `concepts` (default 3; expand to 5 only when the user or run template explicitly asks)
- each concept includes:
  - angle
  - mapped objection/desire
  - recommended archetype
  - 3 hooks
  - filming beats
  - breakout rationale
- `first_test_recommendation`

## Workflow
1. Choose 3 default concepts that cover different buyer tensions.
2. Attach each concept to one primary pattern.
3. Produce 3 non-redundant hooks per concept.
4. Add filming beats that creators can execute quickly.
5. Select one first test by speed + likely lift.

## Quality bar
- Concepts feel category-native.
- Hooks are specific and shootable.
- Rationales link back to pattern outlier logic.
- First test recommendation is concrete.
