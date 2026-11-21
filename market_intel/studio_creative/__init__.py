"""Content studio brief, concepts, script and brand-checked deliverables."""

from pathlib import Path

from .brief import build_brief, write_json
from .commerce import listing_copies, test_plan, visuals
from .copy import build_script, concepts, preflight, variants_for

__all__ = ["build_brief", "concepts", "generate"]


def generate(run_dir, brief, patterns, concept, reference=None):
    from market_intel.studio.runs import progress

    root = Path(run_dir)
    progress("Writing the voiceover and on-screen copy")
    script = build_script(brief, patterns, concept, reference, root=root)
    progress("Preparing the script variants and checking product claims")
    variants = variants_for(script, concept, brief)
    pattern = next((p for p in patterns if p["id"] == concept["pattern_ref"]), {})
    for v in variants:
        v["preflight"] = preflight(v["script"], pattern, brief)
    progress("Rendering ads and marketplace artwork")
    ads, modules = visuals(root, brief, concept)
    progress("Writing copy for Amazon, Flipkart and Nykaa")
    listings = listing_copies(root, brief)
    data = {
        "concept_id": concept["id"],
        "script": script,
        "variants": variants,
        "statics": ads,
        "aplus": modules,
        "listings": listings,
        "test_plan": test_plan(variants),
        "checks": preflight(script, pattern, brief),
        "lineage": [
            {
                "from": s["insight_ref"],
                "to": s["id"],
                "via": concept["id"],
                "pattern": s["pattern_ref"],
                "frame": s["image"],
            }
            for s in script["shots"]
        ],
    }
    write_json(root / "script.json", script)
    write_json(root / "variants.json", variants)
    write_json(root / "creative.json", data)
    return data
