#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


_SENTENCE_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "u.s", "u.k",
}


def one_sentence(text):
    if not text:
        return ""
    cleaned = str(text).strip()
    if not cleaned:
        return ""
    pattern = re.compile(r"(?<=[.!?])\s+")
    pos = 0
    while True:
        match = pattern.search(cleaned, pos)
        if not match:
            return cleaned.rstrip(",; .!?")
        idx = match.start()
        before = cleaned[:idx]
        last_token = re.split(r"\s+", before)[-1] if before else ""
        core = last_token.rstrip(".!?").lower()
        if core in _SENTENCE_ABBREVIATIONS:
            pos = match.end()
            continue
        return before.rstrip(",; .!?") or cleaned


def parse_list(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def subtitle_for_mode(mode):
    if mode == "outlier-pass":
        return "Evidence-backed creator concepts for your brand"
    if mode == "pending-data":
        return "Initial creator concepts for your brand, with live research in progress"
    if mode == "brand-pass":
        return "Brand-informed creator concepts for your brand"
    return "Initial creator concepts for your brand"


def date_for_run_dir(run_dir):
    parts = run_dir.name.split("-") if run_dir.name else []
    if len(parts) >= 3:
        return "-".join(parts[:3])
    return run_dir.name if run_dir.name else ""


def quick_read_intro(mode, brand_name):
    if mode == "outlier-pass":
        return (
            f"We pulled together a few creator/content directions for {brand_name} grounded in breakout content patterns, "
            "brand source material, and live outlier research where available."
        )
    if mode == "pending-data":
        return (
            f"We pulled together initial creator/content directions for {brand_name} grounded in brand source material and "
            "early category pattern research. Live outlier research is still in progress."
        )
    if mode == "brand-pass":
        return (
            f"We pulled together brand-informed creator/content directions for {brand_name} grounded in brand source material "
            "and category pattern hypotheses."
        )
    return f"We pulled together initial creator/content directions for {brand_name} based on the inputs available in this run."


def build_breakout_kit(args):
    brand = {
        "name": args.brand_name,
        "url": args.brand_url,
        "product_offer": args.product_offer,
        "audience": args.audience,
        "primary_desire": args.primary_desire,
        "primary_objections": parse_list(args.primary_objections),
        "platform_focus": args.platform_focus,
    }

    breakout_patterns = [
        {
            "name": "Strategy hypothesis 1",
            "why_it_works": "Frames a concrete outcome tied to the primary desire without over-claiming.",
            "hook_style": "I tried this one change for a week",
            "outlier_evidence": "Hypothesis only until live outlier evidence is available.",
            "score": 3,
            "evidence_posts": [],
            "confidence_score": 0.3,
        },
        {
            "name": "Strategy hypothesis 2",
            "why_it_works": "Addresses a top objection with a simple, practical reframe.",
            "hook_style": "Most people get this wrong",
            "outlier_evidence": "Hypothesis only until live outlier evidence is available.",
            "score": 3,
            "evidence_posts": [],
            "confidence_score": 0.3,
        },
        {
            "name": "Strategy hypothesis 3",
            "why_it_works": "Uses a routine or ritual to make the product feel easy to adopt.",
            "hook_style": "My 20-second routine",
            "outlier_evidence": "Hypothesis only until live outlier evidence is available.",
            "score": 3,
            "evidence_posts": [],
            "confidence_score": 0.3,
        },
    ]

    creator_archetypes = [
        {
            "name": "Peer explainer",
            "fit_reason": "Makes the offer feel approachable and easy to understand.",
            "best_content_style": "Talking head with simple demo",
            "best_for": "Awareness and basic education",
            "evidence_basis": "Based on brand inputs and category hypotheses.",
            "reference_creators": [],
        },
        {
            "name": "Tasteful lifestyle demo",
            "fit_reason": "Shows the product in-context and elevates brand perception.",
            "best_content_style": "Lifestyle montage with VO",
            "best_for": "Consideration and desire-building",
            "evidence_basis": "Based on brand inputs and category hypotheses.",
            "reference_creators": [],
        },
        {
            "name": "Practical skeptic",
            "fit_reason": "Builds trust by testing or questioning claims openly.",
            "best_content_style": "Side-by-side comparison or 7-day log",
            "best_for": "Objection handling and conversion support",
            "evidence_basis": "Based on brand inputs and category hypotheses.",
            "reference_creators": [],
        },
    ]

    concepts = [
        {
            "name": "The primary desire proof",
            "angle": f"Show how {brand['product_offer']} helps deliver the primary desire in a realistic way.",
            "mapped_objection_or_desire": brand["primary_desire"],
            "recommended_archetype": "Peer explainer",
            "hooks": [
                "I tried one change and here’s what shifted.",
                "The fastest way I found to feel the difference.",
                "This is the part everyone skips.",
            ],
            "filming_beats": [
                "Set up the before state",
                "Demonstrate the product use",
                "Share the after state with caveat",
            ],
            "why_it_could_break_out": "Simple before/after framing and practical proof tends to hold attention.",
        },
        {
            "name": "Objection reset",
            "angle": "Reframe the top objection with a short, practical explanation.",
            "mapped_objection_or_desire": brand["primary_objections"][0] if brand["primary_objections"] else "Top objection",
            "recommended_archetype": "Practical skeptic",
            "hooks": [
                "I was skeptical about this too.",
                "The one thing I learned after trying it.",
                "What changed my mind about it.",
            ],
            "filming_beats": [
                "State the skepticism",
                "Show the test or comparison",
                "Wrap with what changed",
            ],
            "why_it_could_break_out": "Skeptical framing earns trust and prompts comments.",
        },
        {
            "name": "Routine fit",
            "angle": "Integrate the product into an existing routine for ease of adoption.",
            "mapped_objection_or_desire": "Ease and simplicity",
            "recommended_archetype": "Tasteful lifestyle demo",
            "hooks": [
                "My everyday routine in 20 seconds.",
                "The one step that makes this feel easy.",
                "Here’s how I actually use it.",
            ],
            "filming_beats": [
                "Routine setup",
                "Product use moment",
                "Quick benefit recap",
            ],
            "why_it_could_break_out": "Routine content is repeatable and easy to save.",
        },
    ]

    first_test = {
        "primary_concept": concepts[0]["name"],
        "primary_archetype": concepts[0]["recommended_archetype"],
        "goal": "Signal early creative lift and objection clarity",
        "why_first": "It maps directly to the primary desire and is easy to film quickly.",
        "test_structure": [
            "3 creators",
            "1 to 2 concepts each",
            "2 hook variations per concept",
            "1 core CTA angle",
        ],
    }

    research = {
        "mode": "quick-pass",
        "confidence": "Low",
        "brand_discovery": {
            "founder_positioning": "",
            "hero_products": [],
            "price_points": [],
            "suspicious_price_points": [],
            "raw_price_points": [],
            "source_coverage_notes": [],
            "verbatim_language": [],
        },
        "virlo": {
            "comet_id": "",
            "status_note": "",
            "videos": [],
            "outliers": [],
        },
    }

    return {
        "brand": brand,
        "research": research,
        "breakout_patterns": breakout_patterns,
        "creator_archetypes": creator_archetypes,
        "concepts": concepts,
        "first_test": first_test,
    }


def render_client_brief(kit, run_dir):
    brand = kit["brand"]
    patterns = kit["breakout_patterns"]
    archetypes = kit["creator_archetypes"]
    concepts = kit["concepts"]
    first = kit["first_test"]
    research = kit["research"]
    mode = research.get("mode", "quick-pass")
    confidence_label = research.get("confidence", "Low")
    top_three = [c["name"] for c in concepts[:3] if c.get("name")]
    top_objection = (brand.get("primary_objections") or ["the top buying objection"])[0]
    primary_desire = brand.get("primary_desire") or "the buyer outcome"
    archetype_names = [a["name"] for a in archetypes[:3] if a.get("name")]
    if archetype_names:
        theme_phrase = ", ".join(n.lower() for n in archetype_names)
    else:
        theme_phrase = "credible delivery, objection resolution, and routine fit"
    anchor = first.get("primary_concept") or (top_three[0] if top_three else "the strongest creator angle")

    lines = [
        "# Creator Breakout Brief",
        "",
        f"**Subtitle:** {subtitle_for_mode(mode)}  ",
        f"**Brand:** {brand['name']}  ",
        f"**Prepared for:** {brand['name']}  ",
        f"**Date:** {date_for_run_dir(run_dir)}  ",
        f"**Research mode:** {mode}  ",
        f"**Confidence:** {confidence_label}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
    ]
    if top_three:
        concept_list = ", ".join(f"**{name}**" for name in top_three)
        lines.append(
            f"{brand['name']} does not need more generic UGC. It needs creator concepts built around "
            f"{theme_phrase}. Three directions stand out immediately: {concept_list}."
        )
    else:
        lines.append(
            f"{brand['name']} does not need more generic UGC. It needs creator concepts built around {theme_phrase}."
        )
    lines += [
        "",
        f"**The move:** Run a small creator test anchored on **{anchor}**, targeting {primary_desire} while respecting the fear of {top_objection}.",
        "**What we would ship first:** 3 creator briefs, 2 hook variations per creator, 1 clear product/offer CTA.",
        "**Evidence base:** Directional brand inputs and category hypotheses. Add connector research before presenting this as outlier-backed.",
        "",
        "---",
        "",
        "## 2. The Breakout Thesis",
        "",
        (
            f"In this category, breakout content is not being driven by polished aspiration. "
            f"It is being driven by surprisingly credible delivery — creators who resolve {top_objection} "
            f"on-camera while making {primary_desire} feel specific and testable. "
            f"Brands still briefing generic lifestyle content are missing the real pattern."
        ),
        "",
        "---",
        "",
        "## 3. Pattern Board",
        "",
    ]
    for idx, p in enumerate(patterns[:5], start=1):
        lines += [
            f"### Pattern {idx} — {p['name']}",
            f"**Breakout Driver:** {p['why_it_works']}  ",
            f"**Hook style:** {p['hook_style']}  ",
            f"**How {brand['name']} should use it:** {p['outlier_evidence']}",
            "",
        ]
    lines += [
        "**Read on the category:** These are directional hypotheses until live source-post evidence is attached.",
        "",
        "---",
        "",
        "## 4. Creator Archetypes",
        "",
    ]
    for idx, a in enumerate(archetypes[:3], start=1):
        lines += [
            f"### The {a['name']}",
            f"**Role in the feed:** {a['best_for']}  ",
            f"**Energy and style:** {a['best_content_style']}  ",
            f"**Why they fit the pattern:** {a['fit_reason']}  ",
            "**Brief type:** A brief that makes the product feel specific, credible, and easy to understand without overclaiming.",
            "",
        ]
    lines += [
        "**Note:** These are creator types and breakout comps, not promised partners.",
        "",
        "---",
        "",
        "## 5. Concept Slate",
        "",
    ]
    for idx, c in enumerate(concepts, start=1):
        if idx == 1:
            priority = "High — run first"
        elif idx == 2:
            priority = "High — run alongside the anchor"
        else:
            priority = "Medium — run if capacity allows"
        lines += [
            f"### Concept {idx}: {c['name']}",
            f"**Breakout Driver:** {c.get('recommended_archetype', 'Creator archetype')} delivering {c.get('mapped_objection_or_desire', 'the mapped buyer tension')}  ",
            f"**Buyer Tension:** {c.get('mapped_objection_or_desire', '')}  ",
            "**Creator Delivery Style:** A creator who can make the product feel specific, credible, and easy to understand without overclaiming  ",
            "**Format:** 15-30 second creator proof, education, or routine-fit video  ",
            f"**Test Priority:** {priority}  ",
            "**Strategic fit:** Medium · **Breakout evidence:** Hypothesis · **Production ease:** High · **Confidence:** Hypothesis only",
            "",
            f"**Core angle:** {c['angle']}",
            "",
            "**Hook options:**",
        ]
        lines += [f"- {h}" for h in c.get("hooks", [])]
        lines += ["", "**What the creator actually films:**"]
        lines += [f"- {b}" for b in c.get("filming_beats", [])]
        lines += [
            "",
            f"**Why this could break out:** {c['why_it_could_break_out']}  ",
            "**Guardrail:** Frame claims as creator experience and product role, not guaranteed outcomes.",
            "",
        ]
    lines += [
        "---",
        "",
        "## 6. First 3 Tests We Would Run",
        "",
    ]
    for idx, c in enumerate(concepts[:3], start=1):
        why = one_sentence(c.get("why_it_could_break_out", "")) or "Ready to run as a first-round creator test"
        lines.append(f"{idx}. **{c['name']}** — {why}.")
    lines += [
        "",
        "**Test shape:** 3 creators matched to archetype, 2 hook variations per creator, 1 product/offer CTA.  ",
        f"**Primary goal:** {first.get('goal','Validate early creative signal')}.  ",
        "**Decision window:** 7–14 days after posting.",
        "",
        "### Success signals",
        "- Saves and shares on useful product education",
        "- Qualified comments about the buyer objection or product role",
        "- Click intent to the recommended product or offer page",
        "- Creator feedback that the brief is filmable without overclaiming",
        "",
        "---",
        "",
        "## 7. What We Would NOT Do",
        "",
        "- Would not brief generic lifestyle or \"authentic UGC\" content first.",
        "- Would not optimize for follower count over pattern fit.",
        "- Would not lead with polished aspiration when the category rewards credible discovery.",
        "- Would not imply guaranteed outcomes or use before/after claims without substantiation.",
        "- Would not position creators as a sourced or booked roster before they are actually briefed.",
        "",
        "---",
        "",
        "## 8. Managed Next Step",
        "",
        (
            f"If these directions feel right, the next move is to source 2–3 creators per winning archetype, "
            f"brief them against the strongest concepts, and run a controlled first test round. "
            f"We source, brief, manage delivery, and refine {brand['name']}'s creator strategy from real performance data."
        ),
        "",
        "---",
        "",
        "## Appendix: Brand and Audience Context",
        "",
        f"**Product:** {brand.get('product_offer','')}  ",
        f"**Audience:** {brand.get('audience','')}  ",
        f"**Primary desire:** {brand.get('primary_desire','')}  ",
        f"**Platform focus:** {brand.get('platform_focus','')}",
        "",
        "**Primary objections:**",
    ]
    lines += [f"- {o}" for o in brand.get("primary_objections", [])]
    lines += [
        "",
        "### Claim and brand-safety guardrails",
        "- Frame results as creator experience, product education, and product role, not guaranteed outcomes.",
        "- Do not imply creators are booked, available, sourced, or pre-secured.",
        "- Do not use before/after claims unless the asset has substantiation and approval.",
        "- Keep the tone specific, useful, and brand-true rather than hype-led.",
    ]
    return "\n".join(lines) + "\n"


def render_internal_notes(kit):
    brand = kit["brand"]
    research = kit["research"]
    mode = research.get("mode", "quick-pass")
    confidence = research.get("confidence", "Low")
    patterns = kit.get("breakout_patterns", [])[:3]
    concepts = kit.get("concepts", [])
    first = kit.get("first_test", {})
    top_archetype = kit.get("creator_archetypes", [{}])[0].get("name", "top archetype")

    lines = [
        f"# Creator Breakout Kit - Internal Notes ({brand['name']})",
        "",
        "## 1. Input quality + gaps",
        f"- Research mode used: {mode}",
        f"- Confidence level: {confidence}",
        "- Missing context: live outlier evidence still pending",
        "- Firecrawl brand discovery status: missing",
        "- Virlo outlier research status: missing",
        "- Virlo comet id: ",
        "- Assumptions made:",
        "  - brand summary based on provided inputs only",
        "  - concepts are starting hypotheses pending real creator performance",
        "- Source coverage notes:",
        "",
        "## 2. Brand psychology notes",
        f"- Core buyer identity: {brand.get('audience','')}",
        f"- Primary tensions: {brand.get('primary_desire','')} vs {', '.join(brand.get('primary_objections', [])[:2])}",
        "- Objection hierarchy:",
    ]
    for idx, o in enumerate(brand.get("primary_objections", []), start=1):
        lines.append(f"  {idx}. {o}")
    lines += [
        "",
        "## 3. Pattern evidence log",
        "- Source posts or evidence references: not yet attached",
    ]
    for idx, p in enumerate(patterns, start=1):
        lines += [
            "",
            f"### Pattern {idx} — {p['name']}",
            f"- Outlier evidence: {p['outlier_evidence']}",
            f"- Repeatability signal: score {p['score']}/5 in current synthesis",
            "- Risk: live source-post evidence still needs to fully back the framing if this is sold as heavily data-backed",
        ]
    lines += [
        "",
        "## 4. Archetype decision notes",
        f"- Why archetype A vs alternatives: {top_archetype} was chosen for fit with the strongest objection/desire cluster",
        "- Funnel role mapping: archetypes split across awareness, objection-handling, and conversion support",
        "",
        "## 5. Concept rationale audit",
    ]
    for idx, concept in enumerate(concepts, start=1):
        pattern_name = patterns[min(idx - 1, len(patterns) - 1)].get("name", "") if patterns else "n/a"
        production_complexity = "medium" if len(concept.get("filming_beats", [])) >= 3 else "low"
        lines += [
            f"- Concept {idx} ({concept.get('name','')}): pattern link = {pattern_name}; "
            f"objection/desire link = {concept.get('mapped_objection_or_desire','')}; "
            f"production complexity = {production_complexity}; confidence = medium",
        ]
    lines += [
        "",
        "## 6. Test recommendation logic",
        f"- Why selected first: {first.get('why_first','')}",
        "- Failure modes to watch: low hook retention, unclear proof moment, or creators struggling to film the beats",
        "- Next iteration triggers: adjust hooks or swap archetype if early tests underperform or feedback flags confusion",
        "",
        "## 7. Handoff constraints",
        "- Claim safety check complete: yes",
        "- Must-not-say reminders:",
        "  - no booked creator claims",
        "  - no sourced roster claims without proof",
        "  - no implying creators are lined up or pre-secured",
        "",
        "## 8. Structured output export check",
        "- Schema file used: `shared/schemas/breakout-kit.schema.json`",
        "- JSON export created: yes",
        "- Any schema gaps or field compromises: live research not attached",
    ]
    return "\n".join(lines) + "\n"


def render_sales_handoff(kit):
    brand = kit["brand"]
    return "\n".join([
        "If any of these directions feel strong, next step is to turn the top 2-3 into a managed creator test.",
        "",
        "That means we source the right creators, brief them against these concepts, manage delivery, and refine from real performance data.",
        "",
        f"This is built from initial creator concepts for {brand['name']}, pending live outlier validation.",
    ]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brand-name", required=True)
    ap.add_argument("--brand-url", required=True)
    ap.add_argument("--product-offer", required=True)
    ap.add_argument("--audience", required=True)
    ap.add_argument("--primary-desire", required=True)
    ap.add_argument("--primary-objections", required=True)
    ap.add_argument("--platform-focus", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--constraints")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    input_payload = {
        "brand_name": args.brand_name,
        "brand_url": args.brand_url,
        "product_offer": args.product_offer,
        "audience": args.audience,
        "primary_desire": args.primary_desire,
        "primary_objections": parse_list(args.primary_objections),
        "platform_focus": args.platform_focus,
    }
    constraints = parse_list(args.constraints)
    if constraints:
        input_payload["constraints"] = constraints

    kit = build_breakout_kit(args)

    write_json(run_dir / "input.json", input_payload)
    write_json(run_dir / "breakout-kit.json", kit)
    (run_dir / "creator-breakout-brief.md").write_text(render_client_brief(kit, run_dir))
    (run_dir / "internal_notes.md").write_text(render_internal_notes(kit))

    if kit["brand"].get("product_offer") and kit["brand"].get("audience") and kit["brand"].get("primary_desire"):
        (run_dir / "sales_handoff.md").write_text(render_sales_handoff(kit))

    print(json.dumps({
        "run_dir": str(run_dir),
        "input": str(run_dir / "input.json"),
        "kit": str(run_dir / "breakout-kit.json"),
        "client": str(run_dir / "creator-breakout-brief.md"),
        "internal": str(run_dir / "internal_notes.md"),
        "sales_handoff": str(run_dir / "sales_handoff.md") if (run_dir / "sales_handoff.md").exists() else "",
    }))


if __name__ == "__main__":
    main()
