#!/usr/bin/env python3
"""Render a Creator Breakout Brief as a single self-contained HTML file
from a run directory containing breakout-kit.json.

This is the presentation layer sibling of the markdown renderer in
enrich_breakout_run.py. It reuses concept_scores and one_sentence from
that module so confidence labels and first-test copy stay in sync with
the markdown brief.
"""
import argparse
import html as html_lib
import importlib.util
import json
from pathlib import Path


def load_enrich_module():
    path = Path(__file__).with_name("enrich_breakout_run.py")
    spec = importlib.util.spec_from_file_location("enrich_breakout_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def esc(value):
    return html_lib.escape(str(value or ""), quote=True)


def pct_for(label):
    """Map score label to a visual bar width."""
    mapping = {
        "Strong directional": 88,
        "Strong directional signal": 90,
        "Directional": 72,
        "Hypothesis": 55,
        "Hypothesis only": 45,
        "High": 92,
        "Medium": 65,
        "Low": 35,
    }
    return mapping.get(label, 60)


def bar_tone(label):
    if label in ("Strong directional", "Strong directional signal", "High"):
        return ""
    if label in ("Directional", "Medium"):
        return "dim"
    return "warning"


def subtitle_for_mode(mode):
    if mode == "outlier-pass":
        return "Evidence-backed creator concepts for your brand"
    if mode == "pending-data":
        return "Initial creator concepts for your brand, with live research in progress"
    if mode == "brand-pass":
        return "Brand-informed creator concepts for your brand"
    return "Initial creator concepts for your brand"


def archetype_theme_phrase(archetypes):
    names = [a.get("name", "") for a in (archetypes or [])[:3] if a.get("name")]
    if len(names) >= 3:
        return ", ".join(n.lower() for n in names)
    if len(names) == 2:
        return f"{names[0]} and {names[1]}".lower()
    if names:
        return names[0].lower()
    return "credible delivery, objection resolution, and routine fit"


def priority_label(idx):
    if idx == 1:
        return "HIGH · RUN FIRST"
    if idx == 2:
        return "HIGH · RUN ALONGSIDE"
    if idx == 3:
        return "MEDIUM · RUN IF CAPACITY"
    return "BACKLOG"


def priority_class(idx):
    if idx in (1, 2):
        return "high"
    if idx == 3:
        return "medium"
    return ""


def render_top_bar(mode, confidence):
    return f"""
  <div class="terminal-bar">
    <div class="left">
      <span class="brand-mark">◼ CREATOR BREAKOUT KIT · TERMINAL v1</span>
      <span>STRATEGY BEFORE SOURCING</span>
    </div>
    <div class="right">
      <span>MODE: <span class="val" style="color:var(--green)">{esc(mode.upper())}</span></span>
      <span>CONFIDENCE: <span class="val" style="color:var(--green)">{esc(confidence.upper())}</span></span>
      <span><span class="dot"></span>LIVE</span>
    </div>
  </div>
"""


def render_hero(brand):
    name = esc(brand.get("name", "Brand")).upper()
    product = esc(brand.get("product_offer", ""))
    desire = esc(brand.get("primary_desire", ""))
    tail = f"· {product}" if product else ""
    if desire:
        tail = f"{tail} · {desire}" if tail else f"· {desire}"
    return f"""
  <section class="hero">
    <div class="eyebrow">◆ CREATOR BREAKOUT BRIEF</div>
    <h1>What is worth<br><em>actually</em> briefing?</h1>
    <div class="brand-row">
      <span class="key">PREPARED FOR</span>
      <span class="brand">{name}</span>
      <span class="product">{esc(tail)}</span>
    </div>
  </section>
"""


def render_metrics(kit):
    concepts = kit.get("concepts") or []
    patterns = kit.get("breakout_patterns") or []
    archetypes = kit.get("creator_archetypes") or []
    return f"""
  <section class="metrics">
    <div class="metric green">
      <div class="label">Concepts worth testing</div>
      <div class="num" data-count-to="{len(concepts)}">0</div>
      <div class="sub">Pattern-matched, buyer-psych aligned</div>
    </div>
    <div class="metric">
      <div class="label">Breakout patterns detected</div>
      <div class="num" data-count-to="{len(patterns)}">0</div>
      <div class="sub">From post-level outlier signal</div>
    </div>
    <div class="metric red">
      <div class="label">Generic plays rejected</div>
      <div class="num" data-count-to="5">0</div>
      <div class="sub">See "what we would NOT do"</div>
    </div>
    <div class="metric yellow">
      <div class="label">Creator archetypes mapped</div>
      <div class="num" data-count-to="{len(archetypes)}">0</div>
      <div class="sub">Roles, not a roster</div>
    </div>
  </section>
"""


def render_thesis(kit):
    brand = kit.get("brand") or {}
    pov = brand.get("strategic_pov") or ""
    if pov:
        body = esc(pov)
    else:
        objections = brand.get("primary_objections") or []
        top_objection = objections[0] if objections else "buyer hesitation"
        desire = brand.get("primary_desire") or "the desired outcome"
        body = esc(
            f"In this category, breakout content is not being driven by polished aspiration. "
            f"It is being driven by surprisingly credible delivery — creators who resolve {top_objection} "
            f"on-camera while making {desire} feel specific and testable. "
            f"Brands still briefing generic lifestyle content are missing the real pattern."
        )
    return f"""
  <section class="thesis">
    <div class="eyebrow">02 · THE BREAKOUT THESIS</div>
    <blockquote>{body}</blockquote>
  </section>
"""


def render_concept_card(concept, idx, research, patterns, enrich):
    strategic_fit, breakout_evidence, production_ease, confidence = enrich.concept_scores(
        concept, research, patterns
    )
    name = esc(concept.get("name", f"Concept {idx}"))
    archetype = esc(concept.get("recommended_archetype") or "Creator archetype")
    tension = esc(concept.get("mapped_objection_or_desire") or "the mapped buyer tension")
    delivery = esc(concept.get("recommended_archetype") or "Creator who can make the product feel specific and credible without overclaiming")
    hooks = concept.get("hooks") or []
    lead_hook = esc(hooks[0]) if hooks else ""
    anchor_cls = " anchor" if idx == 1 else ""
    priority = priority_label(idx)
    p_cls = priority_class(idx)

    optional_rows = []
    if concept.get("product_focus"):
        optional_rows.append(
            f'<div class="framework-row"><div class="k">Product Focus</div><div class="v">{esc(concept["product_focus"])}</div></div>'
        )
    if concept.get("opening_visual"):
        optional_rows.append(
            f'<div class="framework-row"><div class="k">Opening Shot</div><div class="v">{esc(concept["opening_visual"])}</div></div>'
        )

    callout = ""
    if idx == 1:
        callout = '<div class="callout">This is where budget should go first.</div>'

    return f"""
  <div class="concept{anchor_cls}">
    <div class="concept-head">
      <div class="concept-idx">{idx:02d}</div>
      <div class="concept-name">{name}</div>
      <div class="priority {p_cls}">◼ {priority}</div>
    </div>
    <div class="concept-body">
      <div class="framework">
        <div class="framework-row">
          <div class="k">Breakout Driver</div>
          <div class="v">{archetype} delivering <em>{tension}</em></div>
        </div>
        <div class="framework-row">
          <div class="k">Buyer Tension</div>
          <div class="v">{tension}</div>
        </div>
        <div class="framework-row">
          <div class="k">Creator Delivery Style</div>
          <div class="v">{delivery}</div>
        </div>
        {''.join(optional_rows)}
      </div>
      <div class="bars">
        <div>
          <div class="bar-label"><span>STRATEGIC FIT</span><span class="v">{esc(strategic_fit.upper())}</span></div>
          <div class="bar-track"><div class="bar-fill {bar_tone(strategic_fit)}" style="--fill: {pct_for(strategic_fit)}%"></div></div>
        </div>
        <div>
          <div class="bar-label"><span>BREAKOUT EVIDENCE</span><span class="v">{esc(breakout_evidence.upper())}</span></div>
          <div class="bar-track"><div class="bar-fill {bar_tone(breakout_evidence)}" style="--fill: {pct_for(breakout_evidence)}%"></div></div>
        </div>
        <div>
          <div class="bar-label"><span>PRODUCTION EASE</span><span class="v">{esc(production_ease.upper())}</span></div>
          <div class="bar-track"><div class="bar-fill {bar_tone(production_ease)}" style="--fill: {pct_for(production_ease)}%"></div></div>
        </div>
        <div>
          <div class="bar-label"><span>CONFIDENCE</span><span class="v">{esc(confidence.upper())}</span></div>
          <div class="bar-track"><div class="bar-fill {bar_tone(confidence)}" style="--fill: {pct_for(confidence)}%"></div></div>
        </div>
      </div>
      <div class="hook">
        <div class="k">LEAD HOOK</div>
        <div class="v">"{lead_hook}"</div>
      </div>
      {callout}
    </div>
  </div>
"""


def render_concept_slate(kit, research, patterns, enrich):
    concepts = kit.get("concepts") or []
    if not concepts:
        return """
  <div class="section-head">
    <span class="num">05</span>
    <span class="title">CONCEPT <em>SLATE</em></span>
    <span class="rule"></span>
  </div>
  <div class="concept"><div class="concept-body"><p style="color:var(--fg-soft)">No concepts yet — run the full synthesis pass.</p></div></div>
"""
    cards = "\n".join(
        render_concept_card(c, i + 1, research, patterns, enrich)
        for i, c in enumerate(concepts)
    )
    return f"""
  <div class="section-head">
    <span class="num">05</span>
    <span class="title">CONCEPT <em>SLATE</em></span>
    <span class="rule"></span>
  </div>
{cards}
"""


def render_pattern_board(kit):
    brand = kit.get("brand") or {}
    brand_name = esc(brand.get("name", "the brand"))
    patterns = kit.get("breakout_patterns") or []
    virlo = ((kit.get("research") or {}).get("virlo") or {})
    evidence_cards = virlo.get("evidence_cards") or []

    # Render all evidence cards first (rich content DNA), then fill with
    # simple pattern cards for any breakout_patterns that didn't get an
    # evidence card. This way a run with only one source post still shows
    # all three strategic patterns.
    covered_names = {card.get("pattern", "") for card in evidence_cards}
    items = []
    for card in evidence_cards[:5]:
        items.append(("evidence", card))
    for pattern in patterns[:5]:
        if pattern.get("name", "") in covered_names:
            continue
        if len(items) >= 5:
            break
        items.append(("simple", pattern))

    pattern_html = []
    for idx, (kind, item) in enumerate(items, start=1):
        if kind == "evidence":
            card_name = esc(item.get("pattern", f"Pattern {idx}"))
            driver = esc(item.get("strategic_takeaway", ""))
            mechanic = esc((item.get("content_dna") or {}).get("brick_name") or item.get("pattern", ""))
            how_to = esc(item.get("what_to_borrow", ""))
            ref_url = item.get("source_url", "")
            ref_creator = item.get("creator", "")
            ref = f"REF · {esc(ref_creator)}" if ref_creator else ""
            if ref_url:
                ref = ref + f" · {esc(ref_url)}"
        else:
            card_name = esc(item.get("name", f"Pattern {idx}"))
            driver = esc(item.get("why_it_works", ""))
            mechanic = esc(item.get("hook_style", ""))
            how_to = esc(item.get("outlier_evidence", "Directional hypothesis — validate before briefing."))
            ref = ""
        ref_html = f'<div class="ref">{ref}</div>' if ref else ""
        pattern_html.append(f"""
    <div class="pattern">
      <div class="idx">PATTERN · {idx:02d}</div>
      <h3>{card_name}</h3>
      <div class="row">
        <div class="k">Breakout Driver</div>
        <div class="v">{driver}</div>
      </div>
      <div class="row">
        <div class="k">Reusable Mechanic</div>
        <div class="v">{mechanic}</div>
      </div>
      <div class="row">
        <div class="k">How {brand_name} should use it</div>
        <div class="v">{how_to}</div>
      </div>
      {ref_html}
    </div>
""")

    if not pattern_html:
        pattern_html.append('<div class="pattern"><p style="color:var(--fg-soft)">No patterns yet.</p></div>')

    return f"""
  <div class="section-head">
    <span class="num">03</span>
    <span class="title">PATTERN <em>BOARD</em></span>
    <span class="rule"></span>
  </div>
  <div class="patterns-grid">
    {''.join(pattern_html)}
  </div>
"""


def render_archetypes(kit):
    archetypes = kit.get("creator_archetypes") or []
    cards = []
    for idx, a in enumerate(archetypes[:3], start=1):
        cards.append(f"""
    <div class="archetype">
      <div class="badge">ARCHETYPE · {idx:02d}</div>
      <h4>The {esc(a.get("name", f"Archetype {idx}"))}</h4>
      <div class="row">
        <span class="k">Role in the feed</span>
        <span class="v">{esc(a.get("best_for", ""))}</span>
      </div>
      <div class="row">
        <span class="k">Energy &amp; style</span>
        <span class="v">{esc(a.get("best_content_style", ""))}</span>
      </div>
      <div class="row">
        <span class="k">Why they fit</span>
        <span class="v">{esc(a.get("fit_reason", ""))}</span>
      </div>
    </div>
""")
    if not cards:
        cards.append('<div class="archetype"><p style="color:var(--fg-soft)">No archetypes mapped yet.</p></div>')
    return f"""
  <div class="section-head">
    <span class="num">04</span>
    <span class="title">CREATOR <em>ARCHETYPES</em></span>
    <span class="rule"></span>
  </div>
  <div class="archetypes">
    {''.join(cards)}
  </div>
"""


def render_not_do():
    items = [
        "Brief generic lifestyle or \"authentic UGC\" content first",
        "Optimize for follower count over pattern fit",
        "Lead with polished aspiration when the category rewards credible discovery",
        "Imply guaranteed outcomes or use before/after claims without substantiation",
        "Position creators as a sourced or booked roster before they are actually briefed",
    ]
    lis = "\n".join(f"      <li>{esc(item)}</li>" for item in items)
    return f"""
  <div class="section-head red">
    <span class="num">07</span>
    <span class="title">WHAT WE WOULD <em>NOT</em> DO</span>
    <span class="rule"></span>
  </div>
  <div class="not-do">
    <div class="title-xl">5 generic plays <em>rejected</em></div>
    <div class="sub">THE ANTI-POSITIONING BLOCK · WHAT SHARPENS THE STRATEGY</div>
    <ul>
{lis}
    </ul>
  </div>
"""


def render_first_tests(kit, enrich):
    concepts = kit.get("concepts") or []
    priority_labels = ["RUN FIRST", "RUN ALONGSIDE THE ANCHOR", "RUN IF CAPACITY"]
    cards = []
    for idx, (concept, plabel) in enumerate(zip(concepts[:3], priority_labels), start=1):
        why = enrich.one_sentence(concept.get("why_it_could_break_out", "")) or "Ready to run as a first-round creator test"
        first_cls = " first" if idx == 1 else ""
        cards.append(f"""
    <div class="test{first_cls}">
      <div class="rank">{idx:02d}</div>
      <div class="priority-line">▸ {esc(plabel)}</div>
      <div class="concept-ref">{esc(concept.get("name", f"Concept {idx}"))}</div>
      <div class="why">{esc(why)}.</div>
    </div>
""")
    if not cards:
        cards.append('<div class="test"><p style="color:var(--fg-soft)">Concepts needed before tests can be ranked.</p></div>')
    return f"""
  <div class="section-head">
    <span class="num">06</span>
    <span class="title">FIRST 3 <em>TESTS</em> WE WOULD RUN</span>
    <span class="rule"></span>
  </div>
  <div class="tests">
{''.join(cards)}
  </div>
"""


def render_next_step(brand):
    name = esc(brand.get("name", "the brand"))
    return f"""
  <section class="next">
    <div>
      <div class="title">Source 2–3 creators per winning archetype.<br><em>Then run.</em></div>
    </div>
    <div>
      <p>We source creators against the winning archetypes, brief them against the strongest concepts, manage delivery and approvals, and refine {name}'s creator strategy from real performance data — not guesswork.</p>
      <a class="cta" href="#">Move to managed test</a>
    </div>
  </section>
"""


def render_footer(brand):
    name = esc(brand.get("name", "BRAND"))
    return f"""
  <footer>
    <div><span class="dot">◼</span> CREATOR BREAKOUT KIT · PREPARED FOR {name.upper()}</div>
    <div>STRATEGY BEFORE SOURCING · PATTERN FIT OVER FOLLOWER COUNT</div>
  </footer>
"""


CSS = """
  :root {
    --bg:        #07080a;
    --bg-soft:   #0e1114;
    --bg-card:   #0c1013;
    --line:      #1a1f25;
    --line-2:    #262d35;
    --fg:        #ecece4;
    --fg-soft:   #9ba3ad;
    --fg-dim:    #555c65;
    --green:     #3aff9a;
    --green-dim: #0f8048;
    --yellow:    #ffe600;
    --red:       #ff3d50;
    --red-dim:   #6e1420;
    --mono:      "JetBrains Mono", ui-monospace, Menlo, Consolas, monospace;
    --display:   "Space Grotesk", system-ui, -apple-system, sans-serif;
  }
  *, *::before, *::after { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); font-family: var(--display); -webkit-font-smoothing: antialiased; }
  body {
    background:
      radial-gradient(ellipse 1200px 800px at 10% -10%, rgba(58,255,154,0.05), transparent 60%),
      radial-gradient(ellipse 900px 600px at 110% 10%, rgba(255,230,0,0.035), transparent 60%),
      var(--bg);
    min-height: 100vh;
    overflow-x: hidden;
  }
  .page { max-width: 1320px; margin: 0 auto; padding: 48px 56px 80px; position: relative; z-index: 1; }
  .grid-overlay { position: fixed; inset: 0; background: linear-gradient(rgba(255,255,255,0.012) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.012) 1px, transparent 1px); background-size: 80px 80px; pointer-events: none; z-index: 0; }

  .terminal-bar { display: flex; justify-content: space-between; align-items: center; font-family: var(--mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--fg-soft); padding-bottom: 14px; border-bottom: 1px solid var(--line); position: relative; overflow: hidden; }
  .terminal-bar::after { content: ""; position: absolute; top: 0; bottom: 0; width: 240px; left: -280px; background: linear-gradient(90deg, transparent, rgba(58,255,154,0.28), transparent); animation: sweep 3.6s ease-out 0.2s 1 forwards; pointer-events: none; }
  @keyframes sweep { 0% { left: -280px; opacity: 0; } 10% { opacity: 1; } 90% { opacity: 1; } 100% { left: calc(100% + 40px); opacity: 0; } }
  .terminal-bar .left, .terminal-bar .right { display: flex; gap: 20px; align-items: center; }
  .terminal-bar .right { gap: 28px; }
  .terminal-bar .brand-mark { color: var(--fg); font-weight: 700; letter-spacing: 0.18em; }
  .terminal-bar .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 12px var(--green); margin-right: 8px; animation: pulse 1.6s ease-in-out infinite; vertical-align: middle; }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }

  .hero { padding: 72px 0 56px; border-bottom: 1px solid var(--line); }
  .hero .eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: 0.22em; text-transform: uppercase; color: var(--green); margin-bottom: 24px; }
  .hero h1 { font-size: clamp(64px, 8vw, 128px); line-height: 0.92; letter-spacing: -0.035em; font-weight: 700; margin: 0; color: var(--fg); }
  .hero h1 em { font-style: italic; color: var(--green); font-weight: 500; }
  .hero .brand-row { display: flex; align-items: baseline; gap: 24px; margin-top: 44px; padding-top: 22px; border-top: 1px solid var(--line); font-family: var(--mono); font-size: 13px; text-transform: uppercase; letter-spacing: 0.14em; }
  .hero .brand-row .key { color: var(--fg-dim); }
  .hero .brand-row .brand { color: var(--fg); font-weight: 700; font-size: 22px; letter-spacing: 0.04em; }
  .hero .brand-row .product { color: var(--fg-soft); }

  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; border-bottom: 1px solid var(--line); }
  .metric { padding: 48px 40px 52px; border-right: 1px solid var(--line); position: relative; animation: rise 0.7s ease-out both; }
  .metric:nth-child(1) { animation-delay: 0.2s; }
  .metric:nth-child(2) { animation-delay: 0.3s; }
  .metric:nth-child(3) { animation-delay: 0.4s; }
  .metric:nth-child(4) { animation-delay: 0.5s; border-right: none; }
  @keyframes rise { from { opacity: 0; transform: translateY(18px); } to { opacity: 1; transform: translateY(0); } }
  .metric .label { font-family: var(--mono); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--fg-dim); margin-bottom: 18px; }
  .metric .num { font-family: var(--display); font-size: 104px; line-height: 0.9; letter-spacing: -0.04em; font-weight: 700; color: var(--fg); }
  .metric.green .num { color: var(--green); text-shadow: 0 0 24px rgba(58,255,154,0.35); }
  .metric.red .num { color: var(--red); text-shadow: 0 0 20px rgba(255,61,80,0.25); }
  .metric.yellow .num { color: var(--yellow); text-shadow: 0 0 20px rgba(255,230,0,0.25); }
  .metric .sub { font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em; color: var(--fg-soft); margin-top: 12px; text-transform: uppercase; }

  .thesis { padding: 56px 0; border-bottom: 1px solid var(--line); display: grid; grid-template-columns: 180px 1fr; gap: 48px; align-items: start; }
  .thesis .eyebrow { font-family: var(--mono); font-size: 11px; letter-spacing: 0.2em; text-transform: uppercase; color: var(--green); padding-top: 10px; }
  .thesis blockquote { margin: 0; font-size: clamp(22px, 2.4vw, 34px); line-height: 1.28; letter-spacing: -0.015em; font-weight: 500; color: var(--fg); border-left: 2px solid var(--green); padding-left: 28px; }

  .section-head { display: flex; align-items: baseline; gap: 24px; margin: 72px 0 32px; }
  .section-head .num { font-family: var(--mono); font-size: 13px; color: var(--fg-dim); letter-spacing: 0.2em; }
  .section-head .title { font-size: 36px; font-weight: 700; letter-spacing: -0.02em; color: var(--fg); }
  .section-head .title em { color: var(--green); font-style: normal; }
  .section-head.red .title em { color: var(--red); }
  .section-head .rule { flex: 1; border-top: 1px solid var(--line); }

  .concept { background: var(--bg-card); border: 1px solid var(--line); padding: 36px 40px; margin-bottom: 22px; position: relative; animation: slide-in 0.7s ease-out both; }
  .concept:nth-of-type(1) { animation-delay: 0.8s; }
  .concept:nth-of-type(2) { animation-delay: 0.95s; }
  .concept:nth-of-type(3) { animation-delay: 1.1s; }
  @keyframes slide-in { from { opacity: 0; transform: translateX(-20px); } to { opacity: 1; transform: translateX(0); } }
  .concept.anchor { border-color: var(--green); box-shadow: 0 0 0 1px var(--green-dim), 0 0 40px rgba(58,255,154,0.08); animation: slide-in 0.7s ease-out both, glow 3.2s ease-in-out 1.4s infinite; }
  @keyframes glow { 0%, 100% { box-shadow: 0 0 0 1px var(--green-dim), 0 0 40px rgba(58,255,154,0.08); } 50% { box-shadow: 0 0 0 1px var(--green), 0 0 60px rgba(58,255,154,0.20); } }
  .concept-head { display: flex; align-items: center; gap: 24px; padding-bottom: 24px; border-bottom: 1px solid var(--line); }
  .concept-idx { font-family: var(--mono); font-size: 48px; font-weight: 700; color: var(--fg-dim); letter-spacing: -0.02em; min-width: 72px; }
  .concept.anchor .concept-idx { color: var(--green); }
  .concept-name { font-size: 32px; font-weight: 700; letter-spacing: -0.02em; flex: 1; color: var(--fg); }
  .priority { font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; padding: 10px 16px; border: 1px solid var(--line-2); color: var(--fg-soft); white-space: nowrap; }
  .priority.high { border-color: var(--green); color: var(--green); background: rgba(58,255,154,0.06); }
  .priority.medium { border-color: var(--yellow); color: var(--yellow); background: rgba(255,230,0,0.05); }
  .concept-body { display: grid; grid-template-columns: 1.25fr 1fr; gap: 40px; padding-top: 28px; }
  .framework-row { display: grid; grid-template-columns: 180px 1fr; gap: 20px; padding: 14px 0; border-bottom: 1px dashed var(--line); }
  .framework-row:last-child { border-bottom: none; }
  .framework-row .k { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.16em; color: var(--fg-dim); padding-top: 3px; }
  .framework-row .v { font-size: 15px; color: var(--fg); line-height: 1.45; }
  .framework-row .v em { color: var(--green); font-style: normal; font-weight: 600; }
  .bars { display: flex; flex-direction: column; gap: 16px; padding: 4px 0 0 4px; }
  .bar-label { display: flex; justify-content: space-between; font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.14em; color: var(--fg-soft); margin-bottom: 6px; }
  .bar-label .v { color: var(--fg); font-weight: 700; }
  .bar-track { height: 6px; background: var(--bg-soft); border: 1px solid var(--line); position: relative; overflow: hidden; }
  .bar-fill { position: absolute; top: 0; bottom: 0; left: 0; width: 0; background: var(--green); box-shadow: 0 0 10px rgba(58,255,154,0.4); animation: fill 1.1s cubic-bezier(0.2, 0.8, 0.2, 1) forwards; animation-delay: 1.5s; }
  .concept:nth-of-type(2) .bar-fill { animation-delay: 1.65s; }
  .concept:nth-of-type(3) .bar-fill { animation-delay: 1.8s; }
  .bar-fill.dim { background: var(--yellow); box-shadow: 0 0 10px rgba(255,230,0,0.35); }
  .bar-fill.warning { background: var(--red); box-shadow: 0 0 10px rgba(255,61,80,0.35); }
  @keyframes fill { to { width: var(--fill); } }
  .hook { margin-top: 28px; padding: 20px 24px; background: rgba(58,255,154,0.03); border-left: 2px solid var(--green); grid-column: 1 / -1; }
  .hook .k { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--green); margin-bottom: 8px; }
  .hook .v { font-size: 20px; font-weight: 500; color: var(--fg); font-style: italic; }
  .callout { grid-column: 1 / -1; margin-top: 24px; padding: 18px 24px; background: var(--bg-soft); font-family: var(--mono); font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--yellow); border: 1px dashed var(--yellow); display: flex; align-items: center; gap: 14px; }
  .callout::before { content: "▸"; color: var(--yellow); font-size: 14px; }

  .patterns-grid, .archetypes, .tests { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .pattern, .archetype, .test { background: var(--bg-card); border: 1px solid var(--line); padding: 28px 28px 32px; position: relative; }
  .pattern .idx, .archetype .badge { font-family: var(--mono); font-size: 11px; letter-spacing: 0.18em; color: var(--fg-dim); text-transform: uppercase; }
  .pattern h3 { font-size: 22px; font-weight: 700; margin: 10px 0 18px; letter-spacing: -0.01em; color: var(--fg); line-height: 1.2; }
  .pattern .row, .archetype .row { padding: 12px 0; border-top: 1px solid var(--line); }
  .pattern .row .k, .archetype .row .k { font-family: var(--mono); font-size: 10px; letter-spacing: 0.14em; color: var(--fg-dim); text-transform: uppercase; margin-bottom: 4px; display: block; }
  .pattern .row .v { font-size: 14px; color: var(--fg); line-height: 1.5; }
  .archetype h4 { font-size: 24px; font-weight: 700; letter-spacing: -0.015em; margin: 10px 0 20px; color: var(--fg); }
  .archetype .row .v { color: var(--fg); font-size: 14px; }
  .pattern .ref { margin-top: 16px; font-family: var(--mono); font-size: 10px; color: var(--green); text-transform: uppercase; letter-spacing: 0.12em; word-break: break-all; }

  .not-do { margin-top: 16px; background: repeating-linear-gradient(45deg, transparent 0 18px, rgba(255,61,80,0.03) 18px 19px), var(--bg-card); border: 1px solid var(--red-dim); padding: 36px 40px; position: relative; animation: flicker 5s linear infinite; }
  @keyframes flicker { 0%, 92%, 95%, 100% { border-color: var(--red-dim); } 93%, 94% { border-color: var(--red); box-shadow: 0 0 30px rgba(255,61,80,0.15); } }
  .not-do .title-xl { font-size: 44px; font-weight: 700; letter-spacing: -0.025em; color: var(--fg); margin-bottom: 6px; }
  .not-do .title-xl em { color: var(--red); font-style: italic; text-decoration: line-through; text-decoration-thickness: 3px; text-decoration-color: var(--red); }
  .not-do .sub { font-family: var(--mono); font-size: 11px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--fg-dim); margin-bottom: 26px; }
  .not-do ul { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 14px 40px; }
  .not-do li { display: flex; gap: 16px; padding: 10px 0; border-top: 1px solid var(--line); font-size: 16px; color: var(--fg); line-height: 1.4; }
  .not-do li::before { content: "✕"; color: var(--red); font-weight: 700; font-family: var(--mono); }

  .test.first { border-color: var(--green); background: linear-gradient(180deg, rgba(58,255,154,0.04), var(--bg-card) 70%); }
  .test .rank { font-family: var(--display); font-size: 96px; line-height: 0.9; font-weight: 700; letter-spacing: -0.04em; color: var(--fg-dim); }
  .test.first .rank { color: var(--green); text-shadow: 0 0 20px rgba(58,255,154,0.25); }
  .test .priority-line { font-family: var(--mono); font-size: 10px; letter-spacing: 0.2em; text-transform: uppercase; margin-top: 6px; color: var(--fg-soft); }
  .test.first .priority-line { color: var(--green); }
  .test .concept-ref { font-size: 22px; font-weight: 700; letter-spacing: -0.015em; margin: 22px 0 14px; color: var(--fg); line-height: 1.2; }
  .test .why { font-size: 14px; color: var(--fg-soft); line-height: 1.55; padding-top: 14px; border-top: 1px solid var(--line); }

  .next { margin-top: 72px; padding: 48px 56px; background: var(--bg-card); border: 1px solid var(--line); display: grid; grid-template-columns: 1fr 1fr; gap: 48px; align-items: center; }
  .next .title { font-size: 40px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.05; }
  .next .title em { color: var(--green); font-style: normal; }
  .next p { font-size: 16px; line-height: 1.6; color: var(--fg-soft); margin: 0; }
  .next .cta { display: inline-flex; align-items: center; gap: 12px; font-family: var(--mono); font-size: 12px; letter-spacing: 0.2em; text-transform: uppercase; padding: 16px 24px; background: var(--green); color: #001b10; font-weight: 700; margin-top: 22px; text-decoration: none; }
  .next .cta::after { content: "→"; }

  footer { margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; font-family: var(--mono); font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--fg-dim); }
  footer .dot { color: var(--green); }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition: none !important; }
    .bar-fill { width: var(--fill) !important; }
  }
  @media (max-width: 1100px) {
    .metrics { grid-template-columns: repeat(2, 1fr); }
    .metric:nth-child(2) { border-right: none; }
    .metric:nth-child(1), .metric:nth-child(2) { border-bottom: 1px solid var(--line); }
    .concept-body { grid-template-columns: 1fr; }
    .patterns-grid, .archetypes, .tests { grid-template-columns: 1fr; }
    .not-do ul { grid-template-columns: 1fr; }
    .next { grid-template-columns: 1fr; }
    .thesis { grid-template-columns: 1fr; }
  }
"""


SCRIPT = """
  const animateCount = (el, target, duration = 900, delay = 0) => {
    const start = performance.now() + delay;
    const step = (now) => {
      if (now < start) { requestAnimationFrame(step); return; }
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  document.querySelectorAll('[data-count-to]').forEach((el, i) => {
    const target = parseInt(el.getAttribute('data-count-to'), 10);
    animateCount(el, target, 900, 400 + i * 140);
  });
"""


def render_html(kit, enrich=None):
    enrich = enrich or load_enrich_module()
    brand = kit.get("brand") or {}
    research = kit.get("research") or {}
    patterns = kit.get("breakout_patterns") or []
    mode = research.get("mode", "quick-pass")
    confidence = research.get("confidence", "Low")
    brand_title = esc(brand.get("name", "Brand"))

    body_parts = [
        render_top_bar(mode, confidence),
        render_hero(brand),
        render_metrics(kit),
        render_thesis(kit),
        render_concept_slate(kit, research, patterns, enrich),
        render_pattern_board(kit),
        render_archetypes(kit),
        render_not_do(),
        render_first_tests(kit, enrich),
        render_next_step(brand),
        render_footer(brand),
    ]
    body = "\n".join(body_parts)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=1280" />
<title>Creator Breakout Brief · {brand_title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="grid-overlay"></div>
<div class="page">
{body}
</div>
<script>{SCRIPT}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    kit_path = run_dir / "breakout-kit.json"
    if not kit_path.exists():
        raise SystemExit(f"breakout-kit.json not found at {kit_path}")
    kit = json.loads(kit_path.read_text())
    output = render_html(kit)
    out_path = Path(args.out) if args.out else run_dir / "creator-breakout-brief.html"
    out_path.write_text(output)
    print(json.dumps({"html": str(out_path)}))


if __name__ == "__main__":
    main()
