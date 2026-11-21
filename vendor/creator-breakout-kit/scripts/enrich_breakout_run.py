#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def load_json(path):
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def bullet(lines):
    return "\n".join(f"- {line}" for line in lines if line)


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


def clean_text(value):
    return " ".join(str(value or "").split())


def title_for_video(video):
    title = clean_text(video.get("title"))
    if title:
        return title
    description = clean_text(video.get("description"))
    if len(description) > 140:
        return description[:137].rstrip() + "..."
    return description


def looks_minor_or_child_targeted(video):
    text = f"{video.get('title','')} {video.get('description','')}".lower()
    child_markers = [
        "10-11 yr",
        "10-11 year",
        "10-11yr",
        "10yrs",
        "10 yrs",
        "11 yr old",
        "11 year old",
    ]
    return any(marker in text for marker in child_markers)


def add_video_source(posts, seen_urls, video, outlier=None):
    url = video.get("url")
    if not url or url in seen_urls or looks_minor_or_child_targeted(video):
        return
    seen_urls.add(url)
    outlier = outlier or {}
    posts.append({
        "url": url,
        "creator": video.get("creator") or video.get("creator_url") or outlier.get("creator_url") or "unknown",
        "platform": video.get("platform") or video.get("type") or outlier.get("platform") or "",
        "title": title_for_video(video),
        "views": video.get("views") or video.get("view_count"),
        "outlier_ratio": video.get("outlier_ratio") or outlier.get("outlier_ratio"),
        "matching_topics": outlier.get("matching_topics", []),
        "_search_text": clean_text(" ".join([
            str(video.get("title", "")),
            str(video.get("description", "")),
            " ".join(outlier.get("creator_topics", []) or []),
            " ".join(outlier.get("matching_topics", []) or []),
        ])).lower(),
    })


def keyword_terms(virlo):
    terms = set()
    for phrase in virlo.get("keywords", []) or []:
        phrase = clean_text(phrase).lower()
        if phrase:
            terms.add(phrase)
        for word in phrase.replace("/", " ").split():
            word = word.strip()
            if len(word) >= 6:
                terms.add(word)
    return terms


def score_source_post(post, terms):
    text = post.get("_search_text", "")
    score = 0
    for term in terms:
        if term in text:
            score += 3 if " " in term else 1
    views = post.get("views") or 0
    if views >= 100000:
        score += 2
    elif views >= 10000:
        score += 1
    return score


def promoted_source_posts(virlo, limit=5):
    virlo = virlo or {}
    posts = []
    seen_urls = set()
    for video in virlo.get("videos", []):
        add_video_source(posts, seen_urls, video)
    for outlier in virlo.get("outliers", []):
        for video in outlier.get("videos", []):
            add_video_source(posts, seen_urls, video, outlier)
    terms = keyword_terms(virlo)
    posts = [post for post in posts if score_source_post(post, terms) > 0]
    posts.sort(key=lambda post: (score_source_post(post, terms), post.get("views") or 0), reverse=True)
    return [{k: v for k, v in post.items() if not k.startswith("_")} for post in posts[:limit]]


def format_source_post(post):
    title = post.get("title") or "Untitled post"
    creator = post.get("creator") or "unknown creator"
    platform = post.get("platform") or "unknown platform"
    details = [f"{creator} on {platform}"]
    if post.get("views") is not None:
        details.append(f"{int(post['views']):,} views")
    if post.get("outlier_ratio") is not None:
        details.append(f"{post['outlier_ratio']}x creator outlier")
    return f"{title} - {'; '.join(details)} - {post.get('url','')}"


def render_evidence_card(card):
    lines = [
        f"### Evidence card — {card.get('pattern', 'Source post')}",
        f"**Metadata signal:** {card.get('metadata_signal', '')}  ",
        f"**Video understanding:** {card.get('video_understanding_status', '')}  ",
        f"**Strategic takeaway:** {card.get('strategic_takeaway', '')}  ",
        f"**What we would borrow:** {card.get('what_to_borrow', '')}  ",
        f"**What we would not assume:** {card.get('what_not_to_assume', '')}",
    ]
    dna = card.get("content_dna") or {}
    if dna:
        story = "; ".join(dna.get("story_structure", [])[:4])
        visuals = ", ".join(dna.get("key_visuals", [])[:4])
        lines += [
            f"**Content DNA angle:** {dna.get('angle', '')}  ",
            f"**Hook read:** visual: {dna.get('visual_hook', '')}; text: {dna.get('text_on_screen', '')}; spoken: {dna.get('spoken_line', '')}  ",
            f"**Visual format:** {dna.get('visual_format', '')} ({dna.get('visual_format_confidence', '')})  ",
        ]
        if story:
            lines.append(f"**Story structure:** {story}  ")
        if visuals:
            lines.append(f"**Key visuals:** {visuals}  ")
        lines += [
            f"**Reusable mechanic:** {dna.get('brick_name', '')} — {dna.get('brick_definition', '')}  ",
            f"**Plain-English takeaway:** {dna.get('plain_english_takeaway', '')}",
        ]
    if card.get("source_url"):
        lines.append(f"**Source:** {card.get('source_url')}")
    return "\n".join(lines)


def strategic_hero_products(brand_discovery):
    generic_markers = ["shop all", "best sellers", "all products", "bundle", "starter kit", "the collection"]
    products = []
    for product in (brand_discovery or {}).get("hero_products", []):
        label = clean_text(product)
        if label and not any(marker in label.lower() for marker in generic_markers):
            products.append(label)
    return products[:5]


def evidence_posts_for_render(virlo, limit=5):
    promoted = (virlo or {}).get("promoted_source_posts")
    if promoted:
        return promoted[:limit]
    return promoted_source_posts(virlo, limit=limit)


def ready_audience_signals(research, limit=3):
    audience = ((research.get("virlo") or {}).get("audience_signals") or {})
    signals = []
    for signal in audience.get("signals", []) or []:
        sentiment = signal.get("audience_sentiment") or {}
        if signal.get("report_status") != "ready" or not sentiment.get("overall_summary"):
            continue
        signals.append(signal)
        if len(signals) >= limit:
            break
    return signals


def audience_signal_note(research):
    audience = ((research.get("virlo") or {}).get("audience_signals") or {})
    ready = audience.get("ready_report_count") or len(ready_audience_signals(research))
    pending = audience.get("pending_report_count") or 0
    if ready:
        return f"Virlo audience-sentiment reports were ready for {ready} tracked source target{'s' if ready != 1 else ''}."
    if pending:
        return "Virlo audience-sentiment tracking is queued; rerun the adapter later to pull the generated reports."
    return ""


def audience_signal_source(signal):
    if signal.get("source_url"):
        return signal["source_url"]
    if signal.get("source_creator"):
        return signal["source_creator"]
    return signal.get("tracking_id", "")


def render_client_audience_signal(signal):
    sentiment = signal.get("audience_sentiment") or {}
    labels = ", ".join(sentiment.get("sentiment_labels", [])[:4])
    lines = [
        f"### Audience signal — {audience_signal_source(signal)}",
        f"**What people are reacting to:** {sentiment.get('overall_summary', '')}",
    ]
    if labels:
        lines.append(f"**Mood:** {labels}")
    comments = sentiment.get("notable_comments") or []
    insights = [comment.get("insight") or comment.get("content") for comment in comments if comment.get("insight") or comment.get("content")]
    if insights:
        lines += ["**Comment clues:**"]
        lines += [f"- {insight}" for insight in insights[:3]]
    return "\n".join(lines)


def evidence_base_sentence(research):
    brand_pages = len((research.get("brand_discovery") or {}).get("source_coverage_notes", []))
    video = research.get("video_intelligence") or {}
    coverage = video.get("coverage") or {}
    analyzed = coverage.get("analyzed_count", 0)
    video_assets = coverage.get("video_asset_count", 0)
    transcripts = coverage.get("transcript_count", 0)
    parts = []
    if brand_pages:
        parts.append(f"{brand_pages} brand/site pages")
    if analyzed:
        parts.append(f"{analyzed} breakout TikTok posts")
    if video_assets:
        parts.append(f"{video_assets} video reviews")
    if transcripts:
        parts.append(f"{transcripts} transcript/subtitle reads")
    if parts:
        return "Evidence base: " + ", ".join(parts) + "."
    return "Evidence base: brand inputs and category pattern research."


def client_evidence_note(research):
    video = research.get("video_intelligence") or {}
    coverage = video.get("coverage") or {}
    analyzed = coverage.get("analyzed_count", 0)
    video_assets = coverage.get("video_asset_count", 0)
    transcripts = coverage.get("transcript_count", 0)
    if analyzed:
        detail = f"{analyzed} source posts"
        if video_assets:
            detail += f", including {video_assets} video reviews"
        if transcripts:
            detail += f" and {transcripts} transcript/subtitle reads"
        return f"Evidence note: category patterns were developed from {detail}, plus brand-page review. Final creative should still go through normal brand and claims review."
    return "Evidence note: category patterns should be treated as directional until more source-post evidence is added."


def client_evidence_summary(research):
    video = research.get("video_intelligence") or {}
    coverage = video.get("coverage") or {}
    analyzed = coverage.get("analyzed_count", 0)
    video_assets = coverage.get("video_asset_count", 0)
    transcripts = coverage.get("transcript_count", 0)
    audience_note = audience_signal_note(research)
    if analyzed:
        details = [f"{analyzed} breakout source posts"]
        if video_assets:
            details.append(f"{video_assets} video reviews")
        if transcripts:
            details.append(f"{transcripts} transcript/subtitle reads")
        summary = "Grounded in " + ", ".join(details) + " plus brand-page review."
        return f"{summary} {audience_note}".strip()
    summary = "Grounded in brand-page review and directional category pattern research."
    return f"{summary} {audience_note}".strip()


def short_source(card):
    source = card.get("source_url", "")
    if not source:
        return ""
    creator = card.get("creator") or source
    return f"{creator} ({source})"


def render_client_pattern_card(card, index, brand_name):
    dna = card.get("content_dna") or {}
    mechanic = dna.get("brick_name") or card.get("pattern", "")
    lines = [
        f"### Pattern {index} — {card.get('pattern', 'Pattern')}",
        f"**Breakout Driver:** {card.get('strategic_takeaway', '')}  ",
        f"**Reusable mechanic:** {mechanic}  ",
        f"**How {brand_name} should use it:** {card.get('what_to_borrow', '')}",
    ]
    source = short_source(card)
    if source:
        lines.append(f"**Reference:** {source}")
    return "\n".join(lines)


def render_simple_pattern_card(pattern, index, brand_name):
    how_to_use = pattern.get("outlier_evidence") or "Directional hypothesis — validate with live source-post evidence before briefing this at scale."
    lines = [
        f"### Pattern {index} — {pattern.get('name', f'Pattern {index}')}",
        f"**Breakout Driver:** {pattern.get('why_it_works', '')}  ",
        f"**Hook style:** {pattern.get('hook_style', '')}  ",
        f"**How {brand_name} should use it:** {how_to_use}",
    ]
    return "\n".join(lines)


def concept_scores(concept, research, patterns):
    mode = research.get("mode", "quick-pass")
    has_source_evidence = any((p or {}).get("evidence_posts") for p in (patterns or [])[:3])
    strategic_fit = "High" if concept.get("mapped_objection_or_desire") else "Medium"
    if mode == "outlier-pass" and has_source_evidence:
        breakout_evidence = "Strong directional"
    elif mode == "outlier-pass":
        breakout_evidence = "Directional"
    elif mode in ("brand-pass", "pending-data"):
        breakout_evidence = "Directional"
    else:
        breakout_evidence = "Hypothesis"
    beats = len(concept.get("filming_beats", []) or [])
    production_ease = "High" if beats and beats <= 3 else "Medium"
    if mode == "outlier-pass" and has_source_evidence:
        confidence = "Strong directional signal"
    elif mode in ("outlier-pass", "brand-pass", "pending-data"):
        confidence = "Directional"
    else:
        confidence = "Hypothesis only"
    return strategic_fit, breakout_evidence, production_ease, confidence


def test_priority_label(index):
    if index == 1:
        return "High — run first"
    if index == 2:
        return "High — run alongside the anchor"
    if index == 3:
        return "Medium — run if capacity allows"
    return "Low — backlog for future rounds"


def archetype_brief_type(archetype):
    name = (archetype.get("name") or "").lower()
    if "educator" in name or "explain" in name:
        return "Ingredient or product-role explainer with one clear decision rule."
    if "skeptic" in name or "proof" in name:
        return "Skeptic-reversal or first-use diary that names the fear openly."
    if "routine" in name or "fixer" in name or "demonstrator" in name:
        return "Routine audit or placement demo that simplifies an existing behavior."
    return "A brief that makes the product feel specific, credible, and easy to understand without overclaiming."


def render_creator_archetype(archetype, index):
    name = archetype.get("name", f"Archetype {index}")
    lines = [
        f"### The {name}",
        f"**Role in the feed:** {archetype.get('best_for', '')}  ",
        f"**Energy and style:** {archetype.get('best_content_style', '')}  ",
        f"**Why they fit the pattern:** {archetype.get('fit_reason', '')}  ",
        f"**Brief type:** {archetype_brief_type(archetype)}",
    ]
    return "\n".join(lines)


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


def render_first_three_tests(concepts):
    lines = []
    for idx, concept in enumerate(concepts[:3], start=1):
        why = one_sentence(concept.get("why_it_could_break_out", "")) or "Ready to run as a first-round creator test."
        lines.append(f"{idx}. **{concept['name']}** — {why}.")
    return "\n".join(lines)


def render_what_not_to_do():
    return "\n".join([
        "- Would not brief generic lifestyle or \"authentic UGC\" content first.",
        "- Would not optimize for follower count over pattern fit.",
        "- Would not lead with polished aspiration when the category rewards credible discovery.",
        "- Would not imply guaranteed outcomes or use before/after claims without substantiation.",
        "- Would not position creators as a sourced or booked roster before they are actually briefed.",
    ])


def render_managed_next_step(brand_name):
    return (
        f"If these directions feel right, the next move is to source 2–3 creators per winning archetype, "
        f"brief them against the strongest concepts, and run a controlled first test round. "
        f"We source, brief, manage delivery, and refine {brand_name}'s creator strategy from real performance data."
    )


def archetype_theme_phrase(archetypes, fallback):
    names = [a.get("name", "") for a in (archetypes or [])[:3] if a.get("name")]
    if len(names) >= 3:
        return f"{names[0]}, {names[1]}, and {names[2]}".lower()
    if len(names) == 2:
        return f"{names[0]} and {names[1]}".lower()
    if names:
        return names[0].lower()
    return fallback


def render_executive_summary(kit, research):
    brand = kit["brand"]
    concepts = kit.get("concepts", []) or []
    archetypes = kit.get("creator_archetypes", []) or []
    top_three = [c.get("name", "") for c in concepts[:3] if c.get("name")]
    first_test = kit.get("first_test", {}) or {}
    primary_desire = brand.get("primary_desire") or "the buyer outcome"
    objections = brand.get("primary_objections") or []
    top_objection = objections[0] if objections else "the top buying objection"
    theme_phrase = archetype_theme_phrase(
        archetypes,
        "credible delivery, objection resolution, and routine fit",
    )
    anchor = first_test.get("primary_concept") or (top_three[0] if top_three else "the strongest creator angle")

    lines = []
    if top_three:
        concept_list = ", ".join(f"**{name}**" for name in top_three[:3])
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
        f"**Evidence base:** {client_evidence_summary(research)}",
    ]
    return "\n".join(lines)


def render_breakout_thesis(kit):
    brand = kit["brand"]
    strategic_pov = brand.get("strategic_pov") or ""
    if strategic_pov:
        return strategic_pov
    primary_desire = brand.get("primary_desire") or "the desired outcome"
    objections = brand.get("primary_objections") or []
    top_objection = objections[0] if objections else "buyer hesitation"
    return (
        f"In this category, breakout content is not being driven by polished aspiration. "
        f"It is being driven by surprisingly credible delivery — creators who resolve {top_objection} "
        f"on-camera while making {primary_desire} feel specific and testable. "
        f"Brands still briefing generic lifestyle content are missing the real pattern."
    )


def concept_format(concept):
    archetype = (concept.get("recommended_archetype") or "").lower()
    if "explainer" in archetype or "educator" in archetype:
        return "15-30 second product-role explainer"
    if "demonstrator" in archetype or "real-use" in archetype:
        return "15-30 second real-use demonstration"
    return "15-30 second creator proof or test format"


def creator_profile(concept):
    return "A creator who can make the product feel specific, credible, and easy to understand without overclaiming."


def guardrail_for_concept(concept):
    return "No guaranteed outcomes, no before/after claim unless pre-approved, and keep the result framed as creator experience."


def render_client_concept(concept, index, research, patterns):
    strategic_fit, breakout_evidence, production_ease, confidence = concept_scores(concept, research, patterns)
    archetype = concept.get("recommended_archetype") or "Creator archetype TBD"
    lines = [
        f"### Concept {index}: {concept['name']}",
        f"**Breakout Driver:** {archetype} delivering {concept.get('mapped_objection_or_desire', 'the mapped buyer tension')}  ",
        f"**Buyer Tension:** {concept.get('mapped_objection_or_desire', '')}  ",
        f"**Creator Delivery Style:** {creator_profile(concept)}  ",
        f"**Format:** {concept_format(concept)}  ",
        f"**Test Priority:** {test_priority_label(index)}  ",
        f"**Strategic fit:** {strategic_fit} · **Breakout evidence:** {breakout_evidence} · **Production ease:** {production_ease} · **Confidence:** {confidence}",
        "",
        f"**Core angle:** {concept.get('angle', '')}",
    ]
    if concept.get("product_focus"):
        lines.append(f"**Product focus:** {concept['product_focus']}")
    if concept.get("opening_visual"):
        lines.append(f"**Opening shot:** {concept['opening_visual']}")
    if concept.get("proof_moment"):
        lines.append(f"**Proof moment:** {concept['proof_moment']}")
    if concept.get("creator_selection_criteria"):
        lines.append(f"**Creator selection:** {concept['creator_selection_criteria']}")
    lines += ["", "**Hook options:**"]
    lines += [f"- {hook}" for hook in concept.get("hooks", [])]
    lines += ["", "**What the creator actually films:**"]
    lines += [f"- {beat}" for beat in concept.get("filming_beats", [])]
    if concept.get("cta"):
        lines += ["", f"**CTA:** {concept['cta']}"]
    lines += [
        "",
        f"**Why this could break out:** {concept.get('why_it_could_break_out', '')}  ",
        f"**Guardrail:** {guardrail_for_concept(concept)}",
    ]
    return "\n".join(lines)


def curated_brand_language(brand_discovery):
    raw = brand_discovery.get("verbatim_language", []) or []
    skip_terms = ["subscribe", "10% off", "save now", "sign up", "join our", "learn more", "shop now", "free shipping"]
    terms = []
    for item in raw:
        text = clean_text(item)
        lower = text.lower()
        if not text or any(term in lower for term in skip_terms):
            continue
        # Keep anything that looks like brand voice: a short, declarative phrase that isn't a CTA
        if 4 <= len(text.split()) <= 18:
            terms.append(text)
        if len(terms) >= 5:
            break
    return terms


def render_client_brief(kit, research, run_dir):
    brand = kit.get("brand") or {}
    patterns = kit.get("breakout_patterns") or []
    archetypes = kit.get("creator_archetypes") or []
    concepts = kit.get("concepts") or []
    first = kit.get("first_test") or {}

    brand_discovery = research.get("brand_discovery") or {}
    virlo = research.get("virlo") or {}
    mode = research.get("mode", "quick-pass")
    confidence_label = research.get("confidence", "Medium")
    status_note = virlo.get("status_note")
    evidence_cards = virlo.get("evidence_cards", [])[:5]
    audience_signals = ready_audience_signals(research)
    hero_products = strategic_hero_products(brand_discovery)
    brand_language = curated_brand_language(brand_discovery)

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
        render_executive_summary(kit, research),
    ]
    if status_note:
        lines += ["", f"**Research note:** {status_note}"]
    lines += [
        "",
        "---",
        "",
        "## 2. The Breakout Thesis",
        "",
        render_breakout_thesis(kit),
        "",
        "---",
        "",
        "## 3. Pattern Board",
        "",
    ]
    # Render evidence cards first (rich content DNA from video intelligence),
    # then fill with simple pattern cards for any breakout_patterns that didn't
    # get an evidence card, so a run with only one source post still shows all
    # three strategic patterns.
    covered_names = {card.get("pattern", "") for card in evidence_cards}
    card_idx = 0
    for card in evidence_cards:
        card_idx += 1
        lines += [render_client_pattern_card(card, card_idx, brand["name"]), ""]
    for pattern in patterns[:5]:
        if pattern.get("name", "") in covered_names or card_idx >= 5:
            continue
        card_idx += 1
        lines += [render_simple_pattern_card(pattern, card_idx, brand["name"]), ""]
    lines.append("**Read on the category:** The winning shape is credible, objection-aware creator education, not polished product demo.")
    if audience_signals:
        lines += [
            "",
            "### Audience signals",
            "",
            "Directional signal from comments on tracked source posts. Treat as buyer-language clues for hooks and briefing, not statistically representative market research.",
            "",
        ]
        for signal in audience_signals:
            lines += [render_client_audience_signal(signal), ""]
    lines += [
        "",
        "---",
        "",
        "## 4. Creator Archetypes",
        "",
    ]
    for idx, archetype in enumerate(archetypes[:3], start=1):
        lines += [render_creator_archetype(archetype, idx), ""]
    lines.append("**Note:** These are creator types and breakout comps, not promised partners.")
    lines += [
        "",
        "---",
        "",
        "## 5. Concept Slate",
        "",
    ]
    for idx, concept in enumerate(concepts, start=1):
        lines += [render_client_concept(concept, idx, research, patterns), ""]
    lines += [
        "---",
        "",
        "## 6. First 3 Tests We Would Run",
        "",
        render_first_three_tests(concepts),
        "",
        "**Test shape:** 3 creators matched to archetype, 2 hook variations per creator, 1 product/offer CTA.  ",
        f"**Primary goal:** {first.get('goal', 'Validate whether the strongest creator angles earn saves, qualified comments, and click intent')}.  ",
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
        render_what_not_to_do(),
        "",
        "---",
        "",
        "## 8. Managed Next Step",
        "",
        render_managed_next_step(brand["name"]),
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
    if hero_products:
        lines += [
            "",
            "### Hero products to brief against",
            bullet(hero_products),
        ]
    if brand_language:
        lines += [
            "",
            "### Brand truths to preserve",
            bullet(brand_language),
        ]
    lines += [
        "",
        "### Claim and brand-safety guardrails",
        "- Frame results as creator experience, routine education, and product role, not guaranteed outcomes.",
        "- Avoid regulated or category-sensitive claims unless they are pre-approved.",
        "- Do not imply a product has the same ingredient profile as a source-post reference unless verified product-by-product.",
        "- Do not use before/after claims unless the asset has substantiation and approval.",
        "- Keep the tone specific, useful, and brand-true rather than hype-led.",
    ]
    return "\n".join(lines) + "\n"


def render_internal_notes(kit, research):
    brand = kit["brand"]
    virlo = research.get("virlo") or {}
    brand_discovery = research.get("brand_discovery") or {}
    mode = research.get("mode", "quick-pass")
    confidence = research.get("confidence", "Medium")
    status_note = virlo.get("status_note", "")
    evidence_limitations = research.get("evidence_limitations", [])
    source_posts = evidence_posts_for_render(virlo)
    audience_signals = ready_audience_signals(research)
    audience_note = audience_signal_note(research)
    patterns = kit.get("breakout_patterns", [])[:3]
    archetypes = kit.get("creator_archetypes", [])[:3]
    concepts = kit.get("concepts", [])
    first = kit.get("first_test", {})
    top_archetype = archetypes[0]["name"] if archetypes else "top archetype"

    lines = [
        f"# Creator Breakout Kit - Internal Notes ({brand['name']})",
        "",
        "## 1. Input quality + gaps",
        f"- Research mode used: {mode}",
        f"- Confidence level: {confidence}",
        f"- Missing context: {status_note or 'full live post-level outlier evidence still needs validation across more runs'}",
        f"- Firecrawl brand discovery status: {'complete' if brand_discovery else 'missing'}",
        f"- Virlo outlier research status: {mode if mode in ['pending-data', 'outlier-pass'] else 'missing'}",
        f"- Virlo comet id: {virlo.get('comet_id','')}",
        f"- Virlo audience signal status: {audience_note or 'not run'}",
        "- Assumptions made:",
        f"  - brand summary inferred from site coverage across {len(brand_discovery.get('source_coverage_notes', []))} pages",
        "  - current concept slate still leans on heuristic synthesis where live outlier data is thin",
        f"  - Virlo video understanding limit: {evidence_limitations[0] if evidence_limitations else 'not documented'}",
        "- Source coverage notes:",
    ]
    lines += [f"  - {u}" for u in brand_discovery.get("source_coverage_notes", [])]
    lines += [
        "",
        "## 2. Brand psychology notes",
        f"- Core buyer identity: {brand.get('audience','')}",
        f"- Primary tensions: {brand.get('primary_desire','')} vs {', '.join(brand.get('primary_objections', [])[:2])}",
        "- Objection hierarchy:",
    ]
    for idx, o in enumerate(brand.get("primary_objections", []), start=1):
        lines.append(f"  {idx}. {o}")
    lines += ["", "## 3. Pattern evidence log"]
    if source_posts:
        lines.append("- Source posts or evidence references:")
        for s in source_posts:
            lines.append(f"  - {format_source_post(s)}")
    else:
        lines.append(f"- Source posts or evidence references: {status_note or 'not yet attached'}")
    for idx, p in enumerate(patterns, start=1):
        lines += [
            "",
            f"### Pattern {idx} — {p['name']}",
            f"- Outlier evidence: {p['outlier_evidence']}",
            f"- Repeatability signal: score {p['score']}/5 in current synthesis",
            "- Risk: live source-post evidence still needs to fully back the framing if this is sold as heavily data-backed",
        ]
    evidence_cards = virlo.get("evidence_cards", [])[:3]
    if evidence_cards:
        lines += [
            "",
            "## 4. Content DNA appendix",
            "",
            "Keep this detail internal or move it to an appendix if the client asks for methodology/source mechanics.",
            "",
        ]
        for card in evidence_cards:
            lines += [render_evidence_card(card), ""]
    if audience_signals:
        lines += [
            "",
            "## Audience sentiment appendix",
            "",
            "Treat these as comment-derived audience clues, not statistically representative market research.",
            "",
        ]
        for signal in audience_signals:
            lines += [render_client_audience_signal(signal), ""]
    lines += [
        "",
        "## 5. Archetype decision notes",
        f"- Why archetype A vs alternatives: {top_archetype} was chosen for fit with the strongest objection/desire cluster",
        "- Funnel role mapping: archetypes split across awareness, objection-handling, and conversion support",
        "",
        "## 6. Concept rationale audit",
    ]
    for idx, concept in enumerate(concepts, start=1):
        pattern_name = patterns[min(idx - 1, len(patterns) - 1)].get("name", "") if patterns else "n/a"
        production_complexity = "medium" if len(concept.get("filming_beats", [])) >= 3 else "low"
        confidence_level = "high" if mode == "outlier-pass" else "medium"
        lines += [
            f"- Concept {idx} ({concept.get('name','')}): pattern link = {pattern_name}; "
            f"objection/desire link = {concept.get('mapped_objection_or_desire','')}; "
            f"production complexity = {production_complexity}; confidence = {confidence_level}",
        ]
    lines += [
        "",
        "## 7. Test recommendation logic",
        f"- Why selected first: {first.get('why_first','')}",
        "- Failure modes to watch: low hook retention, unclear proof moment, or creators struggling to film the beats",
        "- Next iteration triggers: adjust hooks or swap archetype if early tests underperform or feedback flags confusion",
        "",
        "## 8. Handoff constraints",
        "- Claim safety check complete: yes",
        "- Must-not-say reminders:",
        "  - no booked creator claims",
        "  - no sourced roster claims without proof",
        "  - no implying creators are lined up or pre-secured",
        "",
        "## 9. Structured output export check",
        "- Schema file used: `shared/schemas/breakout-kit.schema.json`",
        "- JSON export created: yes",
        f"- Any schema gaps or field compromises: {'Virlo evidence still pending on this run' if status_note or not source_posts else 'none'}",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--research-dir")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    research_dir = Path(args.research_dir) if args.research_dir else None
    kit = load_json(run_dir / "breakout-kit.json")
    if not kit:
        raise SystemExit("breakout-kit.json not found")
    candidate_dirs = [run_dir]
    if research_dir:
        candidate_dirs.insert(0, research_dir)
    brand_discovery = None
    virlo = None
    audience_signals = None
    for d in candidate_dirs:
        brand_discovery = brand_discovery or load_json(d / "brand-discovery.json")
        virlo = virlo or load_json(d / "virlo-outlier-research.json")
        audience_signals = audience_signals or load_json(d / "virlo-audience-signals.json")

    mode = "quick-pass"
    confidence = "Medium"

    virlo_videos = (virlo or {}).get("videos", []) if virlo else []
    virlo_outliers = (virlo or {}).get("outliers", []) if virlo else []
    virlo_status_note = (virlo or {}).get("status_note", "") if virlo else ""
    source_posts = promoted_source_posts(virlo)
    if virlo and not virlo_videos and source_posts:
        virlo = dict(virlo)
        virlo["videos"] = source_posts
        virlo["promoted_source_posts"] = source_posts
        virlo_videos = source_posts
    elif virlo and source_posts:
        virlo = dict(virlo)
        virlo["promoted_source_posts"] = source_posts
    if virlo and audience_signals:
        virlo = dict(virlo)
        virlo["audience_signals"] = audience_signals

    if brand_discovery and virlo:
        if virlo_outliers:
            mode = "outlier-pass"
            confidence = "High" if source_posts else "Medium"
        elif virlo_videos or virlo_status_note:
            mode = "pending-data"
            confidence = "Medium"
        else:
            mode = "brand-pass"
            confidence = "Medium"
    elif brand_discovery:
        mode = "brand-pass"
        confidence = "Medium"
    else:
        mode = "quick-pass"
        confidence = "Low"

    research = {
        "mode": mode,
        "confidence": confidence,
        "brand_discovery": brand_discovery,
        "virlo": virlo,
    }

    kit["research"] = {
        "mode": mode,
        "confidence": confidence,
        "brand_discovery": {
            "founder_positioning": (brand_discovery or {}).get("founder_positioning", ""),
            "hero_products": (brand_discovery or {}).get("hero_products", []),
            "price_points": (brand_discovery or {}).get("price_points", []),
            "suspicious_price_points": (brand_discovery or {}).get("suspicious_price_points", []),
            "raw_price_points": (brand_discovery or {}).get("raw_price_points", []),
            "source_coverage_notes": (brand_discovery or {}).get("source_coverage_notes", []),
            "verbatim_language": (brand_discovery or {}).get("verbatim_language", []),
        },
        "virlo": {
            "comet_id": (virlo or {}).get("comet_id", ""),
            "status_note": (virlo or {}).get("status_note", ""),
            "videos": (virlo or {}).get("videos", []),
            "outliers": (virlo or {}).get("outliers", []),
            "promoted_source_posts": (virlo or {}).get("promoted_source_posts", []),
            "audience_signals": (virlo or {}).get("audience_signals", {}),
        },
    }

    client = render_client_brief(kit, research, run_dir)
    internal = render_internal_notes(kit, research)

    json_name = "breakout-kit.enriched.json" if not args.overwrite else "breakout-kit.json"
    client_name = "creator-breakout-brief.enriched.md" if not args.overwrite else "creator-breakout-brief.md"
    internal_name = "internal_notes.enriched.md" if not args.overwrite else "internal_notes.md"

    (run_dir / json_name).write_text(json.dumps(kit, indent=2))
    (run_dir / client_name).write_text(client)
    (run_dir / internal_name).write_text(internal)

    print(json.dumps({
        "json": str(run_dir / json_name),
        "client": str(run_dir / client_name),
        "internal": str(run_dir / internal_name),
        "mode": mode,
        "confidence": confidence,
    }))


if __name__ == "__main__":
    main()
