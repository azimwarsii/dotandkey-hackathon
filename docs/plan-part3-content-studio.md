# Part 3 Plan: Content Research, Testing and Creation Studio

Turns the Part 1–2 findings into marketing material, and adds a **"what's working" research loop** for videos and posts. Every stage can be checked visually: each output shows the inputs, frames, transcript and checks it was built from.

Built on two open-source projects (read on 21 Nov):

| Repo | What it is | Licence | How we use it |
|---|---|---|---|
| **TheMattBerman/creator-breakout-kit** | Python scripts plus skill prompts. **Brand truth → outlier research (Virlo) → video breakdown (ScrapeCreators + Gemini) → creator archetypes → concept slate → "First 3 tests" → HTML brief** | MIT | **Copy its scripts and skills into our repo** as the research and testing engine. Its brand-snapshot step is replaced by our Part 1–2 insight data. |
| **xixihhhh/clipforge** | Next.js 16 app for AI commerce video. Product URL or photo → script → judge panel → storyboard grid → image-to-video (Seedance, Kling, Veo through one Atlas key) or a free stock-plus-TTS path → FFmpeg compose → QC and publish gate → per-platform export. **MCP server with 30 tools**, plus CLI and Docker. | **AGPL-3.0** | Run **unmodified as a sidecar container** and drive it through MCP or HTTP. Unmodified use avoids AGPL obligations on our code. |

---

## 0. What we reuse vs build

| Requirement | Source |
|---|---|
| Find videos and posts that are working in the niche | Breakout kit: Virlo outliers. **Plus ours:** competitor-account outliers through ScrapeCreators, YouTube Data API search, and Crustdata `social` search |
| **Paste a link to deconstruct** | **Ours.** A URL resolver feeds the breakout kit's `video_intelligence.py` flow and our own deterministic breakdown (§2) |
| Break down what's working | Breakout kit prompt schema (hook, beats, visual format, audio, "portable bricks") plus our frame, OCR and cut analysis, so every claim is visible |
| Patterns → concepts → test plan | Breakout kit skills: `breakout-pattern-research`, `creator-archetype-mapper`, `creator-concept-generator`, and the "First 3 tests" and "What we would NOT do" sections |
| Ad scripts | Ours (Claude, grounded in the Insight Brief and patterns), then the ClipForge **script judges** (pacing, spoken voice, freshness, structure) |
| Storyboards | ClipForge **storyboard grid** (≤9 shots in one 3×3 image, consistent person and product), plus our shot-list table |
| Promo video concept | Concept card from the breakout kit, plus ClipForge **viral replication**: ffmpeg scene cuts give a rhythm skeleton, and the script matches its shot count and durations |
| Marketing video or ad film | ClipForge: `ingest_product` (dotandkey.com URL) → `import_script` → one-tap film or the free path → `contact_sheet`, `qc`, `gate` → `export_platform` |
| Static ads (Meta, Google, marketplace banners) | **Ours:** HTML/CSS templates rendered to PNG with Playwright. The background comes from an image model; the real product photo and the text are composited, never AI-drawn. ClipForge `cover` and `carousel` handle video thumbnails and carousels. |
| Product descriptions, A+ content, listing copy | **Ours:** Claude with a locked fact sheet and deterministic validators |

---

## 1. Inputs: the "Insight Brief" (from Parts 1–2)

A per-product JSON file that every generator reads. **Nothing may claim anything outside it.**

```json
{
  "product": {"handle", "title", "price", "size", "hero_ingredients", "spf", "images", "url"},
  "allowed_claims": ["from catalog body_html + tags only"],
  "audience": {"skin_types", "age_band", "language": ["en", "hinglish"], "top_desires", "top_objections"},
  "strengths": ["SWOT rows with evidence quotes"],
  "weaknesses_to_avoid_in_messaging": [],
  "competitor_weaknesses": ["e.g. Brand X: white cast, NSS −0.4"],
  "trends": ["e.g. 'skin tint', 'ceramide' ↑2.1×"],
  "gaps": [],
  "brand_kit": {"colors", "fonts", "logo", "tone_words", "do_not_say"}
}
```

- The **brand kit** is extracted deterministically from dotandkey.com (CSS colour variables, font-face, logo SVG, product-copy tone) and overridden by official guidelines if Dot & Key share them.
- This file **replaces the breakout kit's Firecrawl `brand-snapshot`**. It is better grounded, because objections come from real 1–2★ reviews rather than site copy.

---

## 2. Research module: "What's working"

### 2a. Discovery: finding winning videos and posts automatically
Ranked by reliability:

1. **Competitor-account outliers (main path, deterministic).**
   - Take the Instagram and YouTube handles of the top-5 competitor brands from Part 1, plus 10–20 Indian skincare creators.
   - Pull their last ~50 posts through ScrapeCreators.
   - Compute `outlier_ratio = views / median(views of that account's last 50 posts)`, as in the breakout kit, plus engagement, comment and share rates.
   - Anything ≥ 3× its own baseline is a "breakout".
2. **Keyword or niche search:**
   - YouTube Data API (free quota) for `sunscreen review india`, `#skincareroutine` Shorts, with view and like counts
   - Virlo comets (paid; the breakout kit's default) for cross-platform outliers
   - Crustdata `/web/search/live` with `sources: ["social"]` or `site: instagram.com/reel`, used as a URL finder
3. **Static ad research:** competitor pages in the Meta Ad Library, through a pasted link or screenshot. Ads running ≥ 30 days are a proxy for winners.

> TikTok is banned in India, so **Reels and Shorts are the target platforms**. TikTok stays usable only as a pattern reference.

### 2b. Paste a link (the dependable path)
A user who likes a post pastes the URL, or drags in an mp4 or screenshots:

```
URL ─► detect platform (IG reel/post/carousel, YT Shorts/video, TikTok, FB, Meta Ad Library)
    ─► fetch: ScrapeCreators (metadata + play_url + transcript)  ─fail─►  yt-dlp (local)  ─fail─►  "upload the file"
    ─► same deconstruct pipeline as discovered posts
    ─► saved to the Swipe File with label  evidence = "user-curated"  (vs "outlier-backed")
```

- The breakout kit's `video_intelligence.py` already handles TikTok and Instagram through ScrapeCreators. We add YouTube (via yt-dlp) and image posts.
- The evidence label is kept honest, following the kit's own "missing data downgrades the label" rule.

### 2c. Deconstruct: deterministic first, model second, everything visible

| Layer | Tool | Output shown in the UI |
|---|---|---|
| Shots and pacing | ffmpeg scene detect (the same detector as ClipForge `contact_sheet`) | **Contact sheet with cut markers**, shot lengths, cuts per second |
| Keyframes | first frame, plus 1 per shot, plus frames at 0–3 s | Filmstrip; the **hook frames** get a highlight |
| Speech | faster-whisper, local and free; handles Hindi and Hinglish | Timestamped transcript aligned under the filmstrip |
| On-screen text | OCR (PaddleOCR or Tesseract) on keyframes | Text overlays with timestamps, and seconds until the first text appears |
| Audio | loudness and VAD: speech ratio, music presence, silence | Waveform with speech and music bands |
| Faces and product | OpenCV or mediapipe face detection; product on screen by matching against catalog images | "Face in first second?", "Product visible at t=" |
| Image posts and carousels | OCR, colour palette (k-means), text density, layout grid, face and product presence | Annotated slide strip |
| **Semantic read (1 model call)** | **Claude with the same keyframes, transcript and OCR the user sees.** Uses the breakout kit's JSON schema: hook type, story beats, format, emotion, primary driver, portable bricks | Card where each field **links to the frame or line it came from** |

The model only sees evidence that is also on screen. A field it cannot ground is marked "inferred" (the kit's evidence rule).

### 2d. Pattern board
- Cluster the deconstructed posts by hook type, format, length band, pacing band and text-overlay style. The clustering is deterministic.
- Then run the breakout kit's `breakout-pattern-research` skill to name 3–5 patterns.
- Each pattern card shows **its supporting posts as thumbnails**, median outlier ratio, repeatability (number of creators) and brand fit.
- A **"winning spec"** per pattern feeds script generation and the pre-flight score (§4), for example "hook ≤ 1.5 s, face in frame 1, 0.8 cuts/s, text on screen by 1 s, 20–35 s".

---

## 3. Generation module

**Flow:** Insight Brief + pattern board → **concept slate** (breakout kit `creator-concept-generator`: angle, mapped objection or desire, archetype, 3 hooks, filming beats, breakout rationale) → the user picks a concept → the assets below are generated.

### 3a. Ad scripts and storyboards
1. Claude writes the script in a strict JSON shot list: `shot#, duration, visual, on-screen text, VO line, insight_ref, pattern_ref`. **Every line carries a provenance tag**, e.g. "uses strength: no white cast (n=312)" or "uses pattern: honest-flaw opener".
2. Run the ClipForge **script judges** (pacing, spoken voice, freshness, structure) and apply the length-preserving rewrites.
3. Optionally **match a reference**: send a pasted winning reel to ClipForge `replicate/analyze` (scene cuts → shot-duration skeleton), so our script fits its rhythm.
4. Storyboard:
   - ClipForge storyboard grid (3×3, consistent presenter and product)
   - our table view: frame, VO, text, provenance

### 3b. Promo video and ad film (ClipForge sidecar, via MCP)

```
clipforge_ingest_product(url=dotandkey.com/products/<handle>)   # real product images, fidelity-locked
clipforge_import_script(projectId, script)                       # our judged script → shots
[Director mode] storyboard grid → AI film (Seedance / Kling / Veo via Atlas key)   # paid; price shown before generating
        or  free path: stock B-roll + Edge TTS (en-IN / hi-IN voices) + compose     # $0 drafts
clipforge_contact_sheet → clipforge_qc → clipforge_gate          # visual + technical verification
clipforge_cover / clipforge_carousel / clipforge_export_platform(Reels 9:16, Shorts, Meta 4:5)
```

- **Use the free path for all drafts.** Generate the paid AI film only for the hero concept.
- **Configure the ClipForge defaults for India.** It ships with China-specific settings: the Chinese AIGC badge, the China ad-law term list, and Douyin QR rules. Switch to an English "AI-generated" label and our own claim guard (§3d).

### 3c. Static ads and e-commerce material

| Asset | Sizes | How it's made |
|---|---|---|
| Meta feed and Stories ads | 1080×1080, 1080×1350, 1080×1920 | HTML template × concept headline × brand kit, rendered to PNG with Playwright |
| Google Display | 300×250, 728×90, 1200×628 | Same templates, responsive |
| Marketplace banners | Amazon Sponsored Brands, Flipkart, Nykaa sizes | Same |
| **A+ content** | Standard modules (header 970×600, 4-image feature, ingredient spotlight, how-to-use, **in-range comparison chart**) | Templates filled from catalog facts. The comparison chart covers **D&K's own range only**, because Amazon A+ does not allow naming competitors. The competitor comparison stays internal. |
| Product description, title, 5 bullets, backend keywords | Per marketplace | Claude with the fact sheet, then validators |

**Image approach:**
- An image model (GPT Image or Gemini, through the same Atlas key or directly) makes **backgrounds and scenes only**.
- The **real Shopify product photo** is cut out with `rembg` (local, free) and composited.
- **Headline and claim text are HTML**: exact brand fonts and colours, never garbled AI text.
- The result is product-accurate and on-brand.

### 3d. Guardrails (deterministic, run on every asset)
- **Claim guard:**
  - every claim must string-match `allowed_claims`
  - banned-term list (India / ASCI-style): fairness or whitening, "cures/treats", "100% safe", "chemical-free", "No.1" or "dermatologist recommended" without proof
  - an SPF number must equal the catalog value
- **Listing validators:** title and bullet character limits per marketplace, backend keyword byte limit, and keyword coverage against the Part 1 search terms.
- **Brand check:** palette distance between the output and the brand colours, logo present, and a tone-lint word list.
- **Video:** ClipForge `qc` and `gate` cover black frames, silence, loudness, hook in the first 3 s and CTA.

---

## 4. Testing module (breakout kit's "test plan", made measurable)

1. **Pre-flight score per script and video variant**, a deterministic rubric against the pattern's winning spec:
   - hook ≤ 1.5 s
   - product on screen ≤ 3 s
   - text overlay by 1 s
   - length inside the winners' interquartile range
   - pacing near the pattern median
   - CTA present
   - claim guard passes

   The score is shown as a checklist, with each fail linking to the shot.
2. **Variant matrix:** for the chosen concept, 3 hooks × 2 formats (talking head vs demo) gives 6 variants, cheap through the free ClipForge path.
3. **Test plan** (breakout kit "First 3 tests"): what to run first, what to run alongside, decision window and success signals (hook rate = 3 s views ÷ impressions, hold rate, CTR, CPA), plus **"What we would NOT do"**.
4. **Read-back loop:** after posting, paste the live post link. It runs through the same deconstruct and metrics pipeline, and its outlier ratio against our own account baseline is logged against the variant. Winners feed back into the pattern board.

---

## 5. "Visually verify every component": the UI contract

Every artifact is a **card** with four panes: **Inputs** (thumbnails, linked evidence) · **Recipe** (prompt, params, model, cost) · **Output** · **Checks** (pass, warn or fail).

The screens:
1. **Swipe File:** grid of discovered and pasted posts with outlier-ratio badges, filterable by brand, pattern and platform.
2. **Deconstruct view:** contact sheet with cuts, hook frames, transcript, OCR timeline, waveform, and the semantic card with grounded links.
3. **Pattern Board:** pattern cards, each with supporting thumbnails and its winning spec.
4. **Concept Slate:** breakout-kit cards (Breakout Driver · Buyer Tension · Creator Style · Test Priority, with a score strip).
5. **Script and Storyboard:** shot table with a provenance chip per line, the 3×3 grid, and the judge diffs (before → after).
6. **Video:** player, ClipForge contact sheet, QC and gate report, platform exports.
7. **Statics and A+:** every size rendered side by side, claim-guard highlights, brand-check score.
8. **Lineage graph:** insight → pattern → concept → script line → shot → frame. Clicking any node opens its card.

**Stack:**
- Next.js UI (ClipForge is Next.js too)
- Python FastAPI backend: Parts 1–2 plus the research module, with the breakout-kit scripts copied in
- ClipForge in Docker (`ghcr.io/xixihhhh/clipforge`), driven over MCP
- Run folders on disk, one per run (breakout-kit style), so every intermediate JSON and image can be inspected

---

## 6. Keys and services

| Service | Used for | Needed? |
|---|---|---|
| Anthropic (Claude) | Semantic deconstruct from frames, concepts, scripts, copy | Yes |
| ScrapeCreators | IG and TikTok post and profile fetch, competitor-account outliers, paste-link resolve | Strongly recommended |
| YouTube Data API | Shorts search and stats | Free; recommended |
| Atlas Cloud (one key in ClipForge) | Image and video models (Seedance, Kling, Veo, GPT Image) | Only for paid hero renders |
| Virlo | Cross-platform niche outlier discovery | Optional (paid) |
| Crustdata | Social and URL discovery fallback | Already have it |
| Local and free | ffmpeg, faster-whisper, OCR, rembg, Playwright, yt-dlp, Edge TTS | Yes |

---

## 7. Build order (hackathon)

1. **Deconstruct pipeline on a pasted link.** URL → fetch → ffmpeg cuts, keyframes, Whisper, OCR → contact sheet → Claude semantic card. This is the most visual demo piece and has no discovery dependency.
2. Swipe File, plus the competitor-account outlier pull for 5 brands.
3. Pattern board, then the concept slate, using the breakout-kit skills with the Insight Brief swapped in.
4. Script JSON with provenance, then the ClipForge sidecar: `ingest_product` → `import_script` → free-path render → `contact_sheet`, `qc`, `gate`.
5. Static ad templates (3 sizes) and listing copy with validators, then the A+ modules.
6. Pre-flight score and test plan, then the paid hero film for the demo product.
7. Lineage graph polish.

**Demo script:**
1. Paste 2 competitor reels → deconstruct live.
2. Show the pattern board → pick a concept.
3. Show the script with provenance chips → storyboard grid → video with contact sheet and gate.
4. Show the statics, A+ content and listing.
5. Show the test plan.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Instagram blocks fetching | ScrapeCreators first, then yt-dlp, then manual upload (always available) |
| AI video generation is slow or costly at demo time | Pre-render the hero film; render live only on the free path |
| ClipForge's China-centric defaults (AIGC badge, ad-law list) | Configure in settings before the demo, and run our India claim guard as the last gate |
| AGPL obligations | Don't modify ClipForge; call it only over MCP or HTTP. If we patch it, publish the patched fork. |
| Model text-in-image errors | Keep all text in HTML, never in generated images |
| Ungrounded "why it worked" claims | The semantic card links each field to a frame or line, and anything unlinked is labelled "inferred" |
