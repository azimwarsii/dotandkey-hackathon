---
name: creator-archetype-mapper
description: Map Creator Breakout Kit breakout patterns and brand buyer psychology to creator archetypes, funnel roles, and honest reference comps. Use after brand snapshot and breakout pattern research when the workflow needs creator types, pattern-to-archetype reasoning, use-case recommendations, and guardrails that avoid claiming creators are booked or sourced.
---

# Creator Archetype Mapper

## Purpose
Translate breakout patterns into creator archetypes that can execute them well.

## Package contract
Use from the `creator-breakout-kit` repo root. Paths are relative to that root.

## Inputs
- `breakout_patterns`
- `hook_styles`
- `brand_snapshot`
- Optional reference creators

## Outputs
- `archetypes` (3)
- `pattern_to_archetype_map`
- `use_case_recommendations` (awareness/objection handling/conversion)
- `do_not_claim_notes` (availability/booking guardrails)

## Workflow
1. Define archetypes by communication style and filming behavior.
2. Map each archetype to strongest applicable patterns.
3. Explain where each archetype is strongest in funnel context.
4. Add references as comps only.

## Guardrails
- Never present archetypes as confirmed creator roster.
- Never imply "already sourced" unless explicitly true.

## Quality bar
- Archetypes are distinct, not synonyms.
- Each archetype has clear content style and role.
- Mapping logic references buyer psychology + pattern evidence.
