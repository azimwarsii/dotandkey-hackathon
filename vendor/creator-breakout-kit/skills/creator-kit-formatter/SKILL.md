---
name: creator-kit-formatter
description: Format Creator Breakout Kit structured output into the shareable Creator Breakout Brief plus internal research notes. Use after concept generation when the workflow needs `creator-breakout-brief.md`, `internal_notes.md`, optional JSON output, claim-safety checks, consistent brief/internal framing, and the shared Creator Breakout Kit style contract.
---

# Creator Kit Formatter

## Purpose
Package outputs into a clean Creator Breakout Brief plus internal research notes.

## Package contract
Use from the `creator-breakout-kit` repo root. Paths are relative to that root.

## Inputs
- Structured kit output from upstream modules
- Optional style constraints

## Outputs
- `creator-breakout-brief.md` (the shareable Creator Breakout Brief)
- `internal_notes.md`
- Optional JSON package for CRM/automation

## Workflow
1. Read `skills/creator-kit-formatter/references/client-brief-template.md`, `skills/creator-kit-formatter/references/internal-notes-template.md`, and `shared/templates/style-profile.md`.
2. If a run directory exists, prefer `python3 scripts/enrich_breakout_run.py --run-dir "$RUN_DIR" --research-dir "$RESEARCH_DIR"` to generate the enriched brief and notes.
3. If formatting manually, populate the shared templates from `shared/schemas/breakout-kit.schema.json`.
4. Verify claims comply with guardrails.
5. Add final test plan and CTA handoff block.

## Brief vs internal split
### The Creator Breakout Brief includes
- concise narrative
- patterns, archetypes, concept slate
- first test recommendation
- managed next step

### The internal notes include
- raw evidence notes
- confidence scores
- assumptions + data gaps
- risk flags for execution

## Quality bar
- The brief is concise and readable.
- Internal notes are decision-dense and auditable.
- Both files remain consistent in claims.

## Style contract
Apply: `shared/templates/style-profile.md` before finalizing client/internal deliverables.
