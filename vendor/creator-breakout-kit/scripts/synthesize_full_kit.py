#!/usr/bin/env python3
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


STAGE_FILES = {
    "brand-snapshot": "brand-snapshot.json",
    "breakout-pattern-research": "breakout-pattern-research.json",
    "creator-archetype-mapper": "creator-archetype-map.json",
    "creator-concept-generator": "concept-slate.json",
    "creator-kit-formatter": ["creator-breakout-brief.md", "creator-breakout-brief.html", "internal_notes.md"],
    "sales-handoff": "sales_handoff.md",
}


def load_json(path):
    path = Path(path)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def load_enrich_module():
    path = Path(__file__).with_name("enrich_breakout_run.py")
    spec = importlib.util.spec_from_file_location("enrich_breakout_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_html_renderer():
    path = Path(__file__).with_name("render_breakout_brief_html.py")
    spec = importlib.util.spec_from_file_location("render_breakout_brief_html", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_briefs(run_dir, kit):
    enrich = load_enrich_module()
    html_renderer = load_html_renderer()
    research = kit.get("research", {})
    (run_dir / "creator-breakout-brief.md").write_text(enrich.render_client_brief(kit, research, run_dir))
    (run_dir / "internal_notes.md").write_text(enrich.render_internal_notes(kit, research))
    (run_dir / "creator-breakout-brief.html").write_text(html_renderer.render_html(kit, enrich=enrich))


def clean_text(value):
    return " ".join(str(value or "").split())


def first_present(values, default=""):
    for value in values:
        if value:
            return value
    return default


def text_blob(*values):
    return clean_text(" ".join(str(value or "") for value in values)).lower()


def post_text(post):
    return text_blob(
        post.get("title"),
        post.get("description"),
        " ".join(post.get("matching_topics", []) or []),
        " ".join(post.get("creator_topics", []) or []),
    )


def post_direct_text(post):
    return text_blob(post.get("title"), post.get("description"))


def match_score(post, include_terms):
    direct = post_direct_text(post)
    combined = post_text(post)
    score = 0
    for term in include_terms:
        if term in direct:
            score += 3
        elif term in combined:
            score += 1
    if post.get("views") is not None:
        score += min(int(post["views"]) / 1000000, 1)
    return score


def pick_post(posts, include_terms, exclude_terms=()):
    fallback = None
    best = None
    best_score = 0
    for post in posts:
        text = post_text(post)
        if fallback is None:
            fallback = post
        if exclude_terms and any(term in text for term in exclude_terms):
            continue
        score = match_score(post, include_terms)
        if score > best_score:
            best = post
            best_score = score
    return best or fallback or {}


def pick_distinct_post(posts, include_terms, used_urls, exclude_terms=()):
    available = [post for post in posts if post.get("url") not in used_urls]
    picked = pick_post(available, include_terms, exclude_terms)
    if picked.get("url"):
        used_urls.add(picked["url"])
    return picked


def post_title(post):
    return clean_text(first_present([post.get("title"), post.get("description")], "Untitled source post"))


def evidence_post(post):
    if not post:
        return {}
    return {
        "post_url": post.get("url", ""),
        "creator": post.get("creator", ""),
        "platform": post.get("platform", ""),
        "views": post.get("views"),
        "outlier_ratio": post.get("outlier_ratio"),
        "title": post_title(post),
        "matching_topics": post.get("matching_topics", []),
    }


def evidence_sentence(post):
    if not post:
        return "No specific source post was promoted; treat this as a synthesis hypothesis."
    parts = [post_title(post)]
    if post.get("views") is not None:
        parts.append(f"{int(post['views']):,} views")
    if post.get("outlier_ratio") is not None:
        parts.append(f"{post['outlier_ratio']}x creator outlier")
    if post.get("creator"):
        parts.append(str(post["creator"]))
    return " | ".join(parts)


def metadata_summary(post):
    title = post_title(post)
    views = f"{int(post['views']):,} views" if post.get("views") is not None else "views unavailable"
    ratio = f"{post['outlier_ratio']}x creator outlier" if post.get("outlier_ratio") is not None else "outlier ratio unavailable"
    topics = ", ".join(post.get("matching_topics", [])[:3]) if post.get("matching_topics") else "topics unavailable"
    return f"{title} ({views}; {ratio}; matching topics: {topics})"


def video_analysis_map(video_intelligence):
    analyses = (video_intelligence or {}).get("analyses") or []
    by_url = {}
    for analysis in analyses:
        meta = analysis.get("_meta") or {}
        source_url = meta.get("source_url")
        if source_url:
            by_url[source_url.rstrip("/")] = analysis
    return by_url


def video_analysis_for_post(post, analyses_by_url):
    url = (post or {}).get("url") or (post or {}).get("post_url")
    if not url:
        return None
    return analyses_by_url.get(url.rstrip("/"))


def video_dna_summary(analysis):
    if not analysis:
        return None
    hook = analysis.get("hook_structure") or {}
    audio = analysis.get("audio") or {}
    performance = analysis.get("performance_analysis") or {}
    return {
        "topic": analysis.get("topic", ""),
        "angle": analysis.get("angle", ""),
        "visual_format": analysis.get("visual_format", ""),
        "visual_format_confidence": analysis.get("visual_format_confidence", ""),
        "visual_hook": hook.get("visual_hook", ""),
        "text_on_screen": hook.get("text_on_screen", ""),
        "spoken_line": hook.get("spoken_line", ""),
        "story_structure": analysis.get("story_structure", []),
        "key_visuals": analysis.get("key_visuals", []),
        "audio_style": audio.get("vo_style", ""),
        "pacing": audio.get("pacing", ""),
        "primary_driver": performance.get("primary_driver", ""),
        "engagement_type": performance.get("engagement_type", ""),
        "brick_name": analysis.get("brick_name", ""),
        "brick_definition": analysis.get("brick_definition", ""),
        "why_it_worked": analysis.get("why_it_worked", ""),
        "plain_english_takeaway": analysis.get("plain_english_takeaway", ""),
        "evidence_quality": analysis.get("evidence_quality", {}),
        "video_asset_sent_to_model": (analysis.get("_meta") or {}).get("video_asset_sent_to_model", False),
        "cover_image_sent_to_model": (analysis.get("_meta") or {}).get("cover_image_sent_to_model", False),
        "transcript_present": (analysis.get("_meta") or {}).get("transcript_present", False),
    }


def build_evidence_card(pattern_name, post, takeaway, borrow, avoid, video_analysis=None):
    card = {
        "pattern": pattern_name,
        "source_url": post.get("url", ""),
        "creator": post.get("creator", ""),
        "platform": post.get("platform", ""),
        "metadata_signal": metadata_summary(post),
        "strategic_takeaway": takeaway,
        "what_to_borrow": borrow,
        "what_not_to_assume": avoid,
        "video_understanding_status": "metadata-only: Virlo provided caption/description, hashtags, topics, thumbnail filename, and performance metrics; no transcript, OCR, frame analysis, or verified scene description.",
    }
    if video_analysis:
        meta = video_analysis.get("_meta") or {}
        if meta.get("video_asset_sent_to_model"):
            status = (
                "video-intelligence: ScrapeCreators video asset, available transcript/subtitles, metadata, and performance metrics were analyzed with Gemini."
            )
        elif meta.get("cover_image_sent_to_model"):
            status = (
                "video-intelligence: ScrapeCreators metadata, available transcript/subtitles, supported cover image, and performance metrics were analyzed with Gemini; visual claims remain confidence-scored."
            )
        else:
            status = (
                "video-intelligence: ScrapeCreators metadata, available transcript/subtitles, and performance metrics were analyzed with Gemini; visual claims remain limited because no video asset or supported cover image was sent."
            )
        card["video_understanding_status"] = (
            status
        )
        card["content_dna"] = video_dna_summary(video_analysis)
    return card


def promoted_posts(research):
    virlo = (research or {}).get("virlo") or {}
    posts = virlo.get("promoted_source_posts") or virlo.get("videos") or []
    return [post for post in posts if post.get("url")]


def build_brand_snapshot(kit):
    brand = kit["brand"]
    discovery = kit.get("research", {}).get("brand_discovery") or {}
    objections = brand.get("primary_objections", [])
    top_objection = objections[0] if objections else "the core buyer objection"
    strategic_pov = (
        f"{brand['name']}'s strongest content wedge is making "
        f"{brand.get('primary_desire', 'the desired outcome')} feel specific, believable, and easy to test, "
        f"while resolving {top_objection} on-camera instead of dodging it."
    )
    return {
        "brand_name": brand["name"],
        "brand_url": brand.get("url", ""),
        "brand_summary": first_present([
            discovery.get("brand_summary"),
            brand.get("product_offer"),
        ]),
        "strategic_pov": strategic_pov,
        "hero_products": discovery.get("hero_products", []),
        "buyer_psychology_map": {
            "audience": brand.get("audience", ""),
            "primary_desire": brand.get("primary_desire", ""),
            "top_objections": objections[:3],
            "core_tension": f"{brand.get('primary_desire', '')} vs {', '.join(objections[:2])}",
        },
        "top_3_objections": objections[:3],
        "top_2_desire_states": [
            brand.get("primary_desire", ""),
            "An approach that feels credible and easy to try without making buyers feel overwhelmed or oversold",
        ],
        "platform_notes": brand.get("platform_focus", ""),
        "source_coverage_notes": discovery.get("source_coverage_notes", []),
        "brand_language_worth_preserving": discovery.get("verbatim_language", [])[:8],
        "confidence": "High" if discovery.get("source_coverage_notes") else "Medium",
    }


def pattern(name, why, hook, cue, post, score):
    return {
        "name": name,
        "why_it_works": why,
        "hook_style": hook,
        "outlier_evidence": f"{cue} Evidence: {evidence_sentence(post)}",
        "score": score,
        "evidence_posts": [evidence_post(post)] if post else [],
        "confidence_score": 0.85 if post else 0.45,
    }


def build_breakout_patterns(kit, posts):
    return [
        pattern(
            "Outcome proof without over-claiming",
            "It maps the product to the buyer's primary desired outcome while staying believable.",
            "I tested the one change that mattered most",
            "Promoted outlier posts are strongest when they make one outcome easy to understand.",
            posts[0] if posts else {},
            4 if posts else 3,
        ),
        pattern(
            "Skeptic-to-believer education",
            "It handles a conversion objection in public instead of pretending the objection does not exist.",
            "I was skeptical until I understood this",
            "Objection-led explanation tends to carry stronger trust than a pure product demo.",
            posts[1] if len(posts) > 1 else {},
            4 if len(posts) > 1 else 3,
        ),
        pattern(
            "Real-use demonstration",
            "It shows the product in an existing behavior, making the next step easier to imagine.",
            "Here is how I actually use it",
            "Real-use framing is repeatable and easy for creators to execute.",
            posts[2] if len(posts) > 2 else {},
            4 if len(posts) > 2 else 3,
        ),
    ]


def build_evidence_cards(patterns, video_intelligence=None, brand_name="the brand"):
    analyses_by_url = video_analysis_map(video_intelligence)
    cards = []
    for item in patterns:
        post = (item.get("evidence_posts") or [{}])[0]
        if not post:
            continue
        synthetic_post = {
            "url": post.get("post_url", ""),
            "creator": post.get("creator", ""),
            "platform": post.get("platform", ""),
            "title": post.get("title", ""),
            "views": post.get("views"),
            "outlier_ratio": post.get("outlier_ratio"),
            "matching_topics": post.get("matching_topics", []),
        }
        video_analysis = video_analysis_for_post(synthetic_post, analyses_by_url)
        pattern_name = item.get("name", "Pattern")
        why = item.get("why_it_works", "")
        hook = item.get("hook_style", "")
        cards.append(build_evidence_card(
            pattern_name,
            synthetic_post,
            why or f"The strategic opportunity is '{pattern_name}' — the structure the source post uses, not its specific content.",
            (
                f"Borrow the '{hook}' framing and the pattern's underlying structure. "
                f"Adapt the mechanic to {brand_name}'s brand truth and product role, not its visual specifics."
            ),
            (
                f"Do not imply the source post proves outcomes for {brand_name} unless the analyzed transcript, "
                "cover image, or reviewed source clearly supports it."
            ),
            video_analysis,
        ))
    return cards


def unique_creators(posts, limit=4):
    creators = []
    seen = set()
    for post in posts:
        creator = post.get("creator")
        if creator and creator not in seen:
            seen.add(creator)
            creators.append(creator)
        if len(creators) >= limit:
            break
    return creators


def build_archetypes(kit, patterns, posts):
    creators = unique_creators(posts)
    return [
        {
            "name": "Evidence-led explainer",
            "fit_reason": "Turns product value into a simple, believable reason to care.",
            "best_content_style": "Talking-head education with product proof",
            "best_for": "Trust and consideration",
            "evidence_basis": patterns[0]["outlier_evidence"],
            "reference_creators": creators,
        },
        {
            "name": "Practical skeptic",
            "fit_reason": "Surfaces and resolves the likely buying objection in a credible voice.",
            "best_content_style": "Skeptical test, comparison, or objection reset",
            "best_for": "Objection handling",
            "evidence_basis": patterns[1]["outlier_evidence"],
            "reference_creators": creators,
        },
        {
            "name": "Real-use demonstrator",
            "fit_reason": "Shows how the product fits into real behavior without overproduction.",
            "best_content_style": "Real-use demo with concise voiceover",
            "best_for": "Desire-building",
            "evidence_basis": patterns[2]["outlier_evidence"],
            "reference_creators": creators,
        },
    ]


def build_concepts(kit):
    brand = kit["brand"]
    objections = brand.get("primary_objections", [])
    discovery = kit.get("research", {}).get("brand_discovery") or {}
    hero_products = discovery.get("hero_products") or []
    hero_product = hero_products[0] if hero_products else brand.get("product_offer", "the hero product")
    primary = brand.get("primary_desire", "the main buyer outcome")
    top_objection = objections[0] if objections else "the top buying objection"
    third_objection = objections[2] if len(objections) > 2 else "Ease of adoption"
    return [
        {
            "name": "The Outcome Proof Test",
            "angle": f"Show the simplest believable path from {brand['name']} to {primary}, without overpromising or overproducing.",
            "mapped_objection_or_desire": primary,
            "recommended_archetype": "Evidence-led explainer",
            "product_focus": hero_product,
            "hooks": [
                f"I tested the one change that actually moved {primary.lower() if isinstance(primary, str) else 'the outcome'}.",
                "Here is what actually changed after a week.",
                "The result was not what I expected.",
            ],
            "filming_beats": [
                "Name the before state in one sentence.",
                "Show the product in believable, unscripted use.",
                "Recap the result with an honest caveat.",
            ],
            "why_it_could_break_out": "It makes the buyer outcome concrete and easy to evaluate in under 30 seconds.",
        },
        {
            "name": "The Objection Reset",
            "angle": f"Handle {top_objection} with a short, useful explanation instead of pretending the objection does not exist.",
            "mapped_objection_or_desire": top_objection,
            "recommended_archetype": "Practical skeptic",
            "product_focus": hero_product,
            "hooks": [
                f"I was skeptical about {brand['name']} too.",
                "Here is what changed my mind.",
                "The part nobody explained clearly.",
            ],
            "filming_beats": [
                "Name the skepticism honestly.",
                "Show the test, comparison, or check.",
                "Close with a clear decision rule.",
            ],
            "why_it_could_break_out": "It earns trust by treating the objection as legitimate and resolving it in public.",
        },
        {
            "name": "The Real-Use Demonstration",
            "angle": f"Show exactly where {brand['name']} belongs in existing behavior, and what changes when it does.",
            "mapped_objection_or_desire": third_objection,
            "recommended_archetype": "Real-use demonstrator",
            "product_focus": hero_product,
            "hooks": [
                f"Here is how I actually use {brand['name']}.",
                "The one step that made this easier.",
                "My real setup, no extra production.",
            ],
            "filming_beats": [
                "Show the current routine or setup.",
                "Slot the product in naturally.",
                "Recap what changed in plain language.",
            ],
            "why_it_could_break_out": "It reduces friction and gives creators a repeatable, on-brand format to execute fast.",
        },
    ]


def build_first_test(concepts):
    return {
        "primary_concept": concepts[0]["name"],
        "primary_archetype": concepts[0]["recommended_archetype"],
        "goal": "Validate whether the strongest creator angle earns saves, qualified comments, and click intent.",
        "why_first": "It attacks the highest-friction buying objection while preserving the brand's positioning.",
        "test_structure": [
            "3 creators matched to the recommended archetypes",
            f"1 primary concept each, with {concepts[0]['name']} as the anchor",
            "2 hook variations per creator",
            "1 CTA: send viewers to the relevant product, offer, or education page",
        ],
    }


def build_sales_handoff(kit):
    brand = kit["brand"]
    concepts = kit["concepts"]
    objections = brand.get("primary_objections", [])
    top_objection = objections[0] if objections else "the highest-friction buying objection"
    support_two = concepts[1]["name"] if len(concepts) > 1 else "the second concept"
    support_three = concepts[2]["name"] if len(concepts) > 2 else "the third concept"
    return "\n".join([
        "# Managed Next Step",
        "",
        "## Recommended lead concept",
        "",
        f"Lead with **{concepts[0]['name']}**. It is the cleanest bridge from the research to a managed creator test because it handles {top_objection} without making {brand['name']} feel generic.",
        "",
        f"Use **{support_two}** and **{support_three}** as support angles. Creator references are comps, not a sourced roster.",
        "",
        "## Sendable follow-up copy",
        "",
        f"We pulled the {brand['name']} brief into three creator-test directions. The strongest starting point is **{concepts[0]['name']}** because it addresses {top_objection} head-on while keeping the brand specific and credible.",
        "",
        f"We would test that alongside **{support_two}** and **{support_three}**. The next step would be sourcing creators against those archetypes, briefing them with the strongest hooks, and using early save/comment/click signal to decide which angle earns more production.",
        "",
        "This is an outlier-informed strategy pass, not a claim that creators are already sourced or ready to post.",
    ]) + "\n"


def stage_manifest(run_dir):
    now = datetime.now(timezone.utc).isoformat()
    stages = []
    for skill, output in STAGE_FILES.items():
        stages.append({
            "skill": skill,
            "status": "materialized",
            "output": output,
        })
    return {
        "generated_at": now,
        "run_dir": str(run_dir),
        "stage_type": "full-kit-synthesis",
        "notes": "This materializes the repository skill stages from connector research and structured inputs.",
        "stages": stages,
    }


def evidence_limitations_for(video_intelligence):
    if video_intelligence and video_intelligence.get("analyses"):
        coverage = video_intelligence.get("coverage") or {}
        if coverage.get("video_asset_count"):
            evidence = "Video intelligence used ScrapeCreators video assets, available transcript/subtitles, metadata, and performance metrics analyzed with Gemini."
        elif coverage.get("cover_image_count"):
            evidence = "Video intelligence used ScrapeCreators metadata, available transcript/subtitles, supported cover images, and performance metrics analyzed with Gemini."
        else:
            evidence = "Video intelligence used ScrapeCreators metadata, available transcript/subtitles, and performance metrics analyzed with Gemini."
        return [
            evidence,
            "Visual details remain confidence-scored from available assets; this is not yet a full frame-by-frame or human-reviewed scene audit unless the analyzed output explicitly says so.",
        ]
    return [
        "Virlo evidence is metadata-only in this run: captions/descriptions, hashtags, creator topics, thumbnail filenames, and performance metrics.",
        "The kit does not yet include transcript, OCR, frame-level, or human-reviewed video-scene analysis.",
    ]


def audience_signal_limitations(audience_signals):
    if not audience_signals:
        return []
    ready = audience_signals.get("ready_report_count") or 0
    pending = audience_signals.get("pending_report_count") or 0
    if ready:
        return [
            f"Virlo Tracking audience sentiment was available for {ready} tracked source target{'s' if ready != 1 else ''}; treat it as comment-derived directional signal, not statistically representative market research.",
        ]
    if pending:
        return [
            "Virlo Tracking audience sentiment is queued but not ready yet; rerun the tracking adapter later to pull the generated reports.",
        ]
    return []


def synthesize(kit, video_intelligence=None):
    research = kit.get("research") or {}
    brand_name = kit.get("brand", {}).get("name", "the brand")
    posts = promoted_posts(research)
    brand_snapshot = build_brand_snapshot(kit)
    patterns = build_breakout_patterns(kit, posts)
    evidence_cards = build_evidence_cards(patterns, video_intelligence, brand_name)
    archetypes = build_archetypes(kit, patterns, posts)
    concepts = build_concepts(kit)
    first_test = build_first_test(concepts)
    confidence = "Medium-High" if len(posts) >= 3 and research.get("brand_discovery") else "Medium"
    audience_signals = (research.get("virlo") or {}).get("audience_signals") or {}

    kit["research"]["confidence"] = confidence
    kit["research"]["evidence_limitations"] = evidence_limitations_for(video_intelligence) + audience_signal_limitations(audience_signals)
    if video_intelligence:
        kit["research"]["video_intelligence"] = video_intelligence
    kit["research"]["virlo"]["evidence_cards"] = evidence_cards
    kit["brand"]["strategic_pov"] = brand_snapshot["strategic_pov"]
    kit["strategy_stage"] = "full-kit-synthesis"
    kit["breakout_patterns"] = patterns
    kit["creator_archetypes"] = archetypes
    kit["concepts"] = concepts
    kit["first_test"] = first_test

    return {
        "kit": kit,
        "brand_snapshot": brand_snapshot,
        "breakout_pattern_research": {
            "research_mode_used": research.get("mode", "quick-pass"),
            "confidence": confidence,
            "source_posts": [evidence_post(post) for post in posts],
            "evidence_limitations": kit["research"]["evidence_limitations"],
            "audience_signals": audience_signals,
            "evidence_cards": evidence_cards,
            "breakout_patterns": patterns,
        },
        "creator_archetype_map": {
            "archetypes": archetypes,
            "pattern_to_archetype_map": [
                {"pattern": patterns[0]["name"], "primary_archetype": archetypes[2]["name"]},
                {"pattern": patterns[1]["name"], "primary_archetype": archetypes[0]["name"]},
                {"pattern": patterns[2]["name"], "primary_archetype": archetypes[1]["name"]},
            ],
            "do_not_claim_notes": [
                "Reference creators are comps, not confirmed roster.",
                "Do not imply creators are booked, available, or pre-secured.",
            ],
        },
        "concept_slate": {
            "concepts": concepts,
            "first_test_recommendation": first_test,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    kit = load_json(run_dir / "breakout-kit.json")
    if not kit:
        raise SystemExit("breakout-kit.json not found")
    video_intelligence = load_json(run_dir / "video-intelligence.json")
    audience_signals = load_json(run_dir / "virlo-audience-signals.json")
    if audience_signals:
        kit.setdefault("research", {}).setdefault("virlo", {})["audience_signals"] = audience_signals

    outputs = synthesize(kit, video_intelligence=video_intelligence)
    write_json(run_dir / "breakout-kit.json", outputs["kit"])
    write_json(run_dir / "brand-snapshot.json", outputs["brand_snapshot"])
    write_json(run_dir / "breakout-pattern-research.json", outputs["breakout_pattern_research"])
    write_json(run_dir / "creator-archetype-map.json", outputs["creator_archetype_map"])
    write_json(run_dir / "concept-slate.json", outputs["concept_slate"])
    write_json(run_dir / "skill-run-manifest.json", stage_manifest(run_dir))
    render_briefs(run_dir, outputs["kit"])
    (run_dir / "sales_handoff.md").write_text(build_sales_handoff(outputs["kit"]))

    print(json.dumps({
        "run_dir": str(run_dir),
        "stage": "full-kit-synthesis",
        "kit": str(run_dir / "breakout-kit.json"),
        "stage_outputs": [
            str(run_dir / file_name)
            for output in STAGE_FILES.values()
            for file_name in ([output] if isinstance(output, str) else output)
            if (run_dir / file_name).exists()
        ],
    }))


if __name__ == "__main__":
    main()
