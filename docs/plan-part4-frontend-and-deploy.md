# Part 4 Plan: One Product Frontend, PWA and Deployment

**Goal:** one app that runs the whole chain from the brief:

> catalog → marketplaces → reviews → competitors → SWOT, gaps and trends → **content** (statics, A+, listing copy, script, storyboard, video) → tests

It uses the visual language of the Outcrowd "zentra" dashboard shot, restyled in Dot & Key branding. It is responsive (mobile and desktop), animated, installable as a PWA, has a first-run walkthrough, and deploys with one command.

**Starting point (21 Nov):**
- **Backend:** FastAPI `market_intel.api`, serving `/category/{c}/report-data`, `/category/{c}/insights` and `/insights/opportunities`, plus the Studio router: 14 routes under `/studio/*` for runs, brief, deconstruct, discover, concepts, generate, film, readback and film-quote.
- **Frontend:** `studio-web/`, a Next.js **16.4.6** and React 19 prototype of about 200 lines covering the Studio only. It uses DM Sans and Instrument Serif and proxies `/studio-api/*` to the backend.
- **ClipForge:** sidecar in `clipforge/compose.yaml`, pinned to a commit and bound to `127.0.0.1:3039`.
- **Uncommitted teammate work:** `market_intel/studio*`, `studio-web/`, `vendor/` and `clipforge/`. **Coordinate before restructuring** (§10).

> ⚠️ `studio-web/AGENTS.md`: Next 16 has breaking changes. Read `node_modules/next/dist/docs/` before writing routing, metadata, manifest or `output` config.

---

## 1. Design system: "zentra" layout × Dot & Key brand

We recreate the **layout and visual language** of the reference: pill nav, big-number cards, hatched step bars, a dot-matrix histogram, a gradient insight card and an "explore next" prompt bar. **We do not copy its assets, logo or name.**

### Tokens

| Token | Value | Source |
|---|---|---|
| `--canvas` | `#EDEDED` page, `#F4F4F4` app frame | Reference |
| `--card` | `#F8F8F8`, a 1px `rgba(255,255,255,.9)` inner highlight, shadow `0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.06)` | Reference |
| Radius | app frame 40px, card 28px, pill 999px, chip 12px | Reference |
| `--ink` | `#1A1A1A` (active nav pill, numbers) | D&K site |
| `--muted` | `#6B7280` (labels), `#B7B7B7` (de-emphasised numbers) | D&K site |
| **`--dk-green`** | **`#82B51C`**, the most-used colour on dotandkey.com: primary data series, positive | D&K site |
| **`--dk-pink`** | **`#FF40B1`** / `#FF3E80`: D&K highlight, step-line series | D&K site |
| `--dk-orange` | `#FF803A`: slash-command chip, warnings | D&K site |
| `--dk-cyan` | `#22BCE0`: competitor series | D&K site |
| Semantic | success `#16A34A`, error `#DC2626` | D&K theme vars |
| Insight gradient | `#FF803A` → `#FF40B1` → `#22BCE0`, plus a grain overlay | Reference gradient card in D&K colours |
| Type | **Poppins** (D&K's brand font, OFL licence, self-hosted). Display numbers 400 weight with `-0.03em` tracking and `tabular-nums`; headings 500; labels 400 | D&K site |
| Logo | the official D&K logo SVG from the dotandkey.com header (to fetch), with a monochrome variant for the app icon | D&K |

**Motifs we keep:**
- **hatched bars:** `repeating-linear-gradient(135deg, …)` for unselected series, with a solid gradient for the selected one
- slanted connectors between bars
- floating value pills ("42%", "Peak: Wed")
- circular `···` menu buttons
- the date-range "compared to" control
- the "What would you like to explore next?" prompt with an orange `/slash` chip

**Light theme only for v1** (Occam's razor). Dark mode is a later add-on via the same tokens.

---

## 2. Information architecture (6 nav items)

Six items stays under Miller's limit and keeps the first and last positions meaningful (serial position effect).

| # | Nav | What it shows (problem statement clause) |
|---|---|---|
| 1 | **Overview** | Home dashboard (§3): the whole market at a glance |
| 2 | **Products** | Catalog grid → product detail: listings on Amazon, Flipkart and Nykaa with price and rating per market, price history and reviews ("extract catalogue, monitor marketplaces, pricing, ratings") |
| 3 | **Competitors** | Top 5 per category in a comparison table and aspect radar, a **new-launch feed**, and brand momentum from Crustdata ("top five competitors, compare offerings, newly launched products") |
| 4 | **Customers** | Aspect sentiment, complaint lift, quotes and the "wish it…" needs ("sentiment: preferences, complaints, strengths, weaknesses") |
| 5 | **Strategy** | SWOT, gaps, trends, forecast, recommendations and GTM ("SWOT, gaps, emerging needs, trends, forecast, improvements, GTM") |
| 6 | **Studio** ✦ | Research → Deconstruct → Patterns → Concepts → Create → Test ("generate marketing content") |

- **Studio** is styled differently (gradient pill) so it stands out (Von Restorff), and it sits last for recency.
- **Global controls** in the top bar:
  - category switcher
  - `as_of` date with "compared to"
  - search (⌘K)
  - help (replay the tour)
- **The one thread through everything:** every insight, gap, complaint or competitor weakness card has a **"Create content from this →"** button. It opens Studio with that evidence attached as the brief, so lineage is preserved. This is how research and content form one product rather than two apps.

---

## 3. Overview: reference widgets mapped to our data

| Reference widget | Our widget | Data (exists today) |
|---|---|---|
| **Payments**: hatched step-bar funnel with a hover tooltip | **Category Opportunity**: one bar per category, sorted by `opportunity_score`. The selected category bar is solid, the others hatched. Tooltip: `Score 0.695 · Forecast +21.7% · D&K share 19.8%` | `/insights/opportunities` → `categories[]` |
| "What would you like to explore next?" prompt with `/chip` | **Ask the market**: slash commands (`/sunscreen`, `/competitors`, `/swot`, `/product watermelon`) navigate instantly. Free text goes to an OpenRouter cheap model **grounded only in the insight JSON, with citations** that open the source card. | new `/api/ask` |
| **Gross Volume**: big number, delta chip, 3 hatched progress rows | **D&K Review Share**: big share %, delta vs the compare date, and rows for Amazon, Flipkart and Nykaa (D&K's average rating and review volume per market) | `score_factors` plus listings |
| **Retention**: pink step line with a "42%" pill | **Demand index**: monthly review-activity step line with a dashed forecast segment and a "+21.7%" pill | `forecast.series` and `projection` |
| **Transactions**: dot-matrix histogram, "Peak: Wed" | **Review velocity**: reviews per week, dots coloured by sentiment, "Peak: <week>" | dated reviews |
| **Customers**: blue dot matrix, "Highest: Thu" | **Competitor launches**: launches per week over 90 days, "Highest: <week>" | catalog diff and launch candidates |
| **Insights**: gradient card with 3 progress segments | **Top insights carousel**: 3 rotating cards (top strength, biggest gap, top recommendation), each with a "Create content →" CTA. The segments auto-advance like stories. | SWOT, gaps and recommendations |
| Date controls ("Jan 01 – Jul 31 compared to …") | `as_of` with "compared to" | the API already accepts `as_of` |
| "Add widget" | **Dropped** (Occam). Replaced by a "Refresh data" button that runs a crawl job with live progress. | crawl CLI as a job |

---

## 4. Studio UX (Part 3 made usable)

A horizontal **stepper**: Research → Deconstruct → Patterns → Concepts → Create → Test. It starts at 1/6 already done ("Brief loaded ✓") for the goal-gradient effect.

- **Research:** a paste-link box that accepts anything (IG, YT, TikTok, FB, an mp4 drag-drop or screenshots) and auto-detects the platform (Postel's law). Below it, the Swipe File grid with outlier-ratio badges.
- **Deconstruct:** filmstrip with cut markers, hook frames, a transcript aligned under the frames, an OCR timeline and a waveform. Semantic fields link to timestamps, so clicking one seeks the video.
- **Patterns and Concepts:** cards showing only the essentials. "Why?" expands the evidence (progressive disclosure).
- **Create:** tabs for Statics · A+ · Listing · Script & Storyboard · Video.
  - Every artifact uses the 4-pane card: Inputs · Recipe (model and ₹/$ cost) · Output · Checks.
  - A **lineage graph** sits in a side drawer.
- **Test:** pre-flight checklist, variant matrix and test plan.
- **Ending (peak-end rule):** finishing a run shows a celebratory "Campaign kit ready" screen. It has a confetti-light animation, a gallery of everything made, and one-click download as a ZIP or share.

---

## 5. UX laws → concrete rules

| Law | Rule in this app |
|---|---|
| Aesthetic-usability | Reference-grade polish: soft shadows, hatched bars, smooth motion. No unstyled states. |
| Visual hierarchy | One hero number per card (48–96px). Labels muted. Only the selected series is saturated. |
| Proximity | Card padding 24–32px and gaps of 16–20px. Related controls sit within 8px of each other. |
| Similarity | D&K = green and competitors = cyan **everywhere**. The same chip style always means "filter". |
| Common region | Every widget is a card. Grouped KPIs share one card (like Gross Volume). |
| Von Restorff | Selected bar is solid; the Studio nav pill is a gradient; the primary CTA is the only dark-filled button on a screen. |
| Hick's law | ≤ 6 nav items, ≤ 3 primary actions per screen, and a ≤ 5-item `···` menu |
| Miller's law | Top-5 competitors, 3 insights in the carousel, 3 concepts by default, chunked lists |
| Jakob's law | Top nav, ⌘K search, standard tables, and a bottom tab bar on mobile, as in familiar apps |
| Occam's razor | No "add widget", no theme picker and no settings sprawl in v1 |
| Tesler's law | The system absorbs complexity: auto platform detection, auto category from the product, and sensible defaults on every generator |
| Progressive disclosure | Evidence, method and thresholds sit behind "Why?" or "Show method". Advanced generator params sit behind "Director mode". |
| Fitts's law | Touch targets ≥ 44px, the primary CTA is bottom-right on desktop and full-width at the bottom on mobile, and the ask bar is always docked |
| Doherty threshold | Every interaction responds in < 400 ms: skeletons immediately, cached GETs, optimistic UI, prefetch on hover, and long jobs as 202 + **SSE progress** |
| Postel's law | Paste box takes any URL or file, the search is fuzzy, dates accept "last 90 days" |
| Feedback loops | Button press animation, toasts, job progress with stage names, and inline validation |
| Recognition over recall | Recent items, a visible breadcrumb of the current category and product, and lineage chips on every artifact |
| Serial position | Overview first, Studio last. The most important KPI goes top-left and the CTA ends each flow. |
| Goal-gradient | The Studio stepper and the walkthrough progress both start partly filled |
| Peak-end | A peak of "insight reveal" animations on Overview and a "Campaign kit ready" ending |

---

## 6. Responsive and motion

**Breakpoints:**

| Width | Layout |
|---|---|
| ≥ 1280 | Reference 3-column grid with the framed app (40px radius) |
| 768–1279 | 2 columns, frameless |
| < 768 | 1 column |

**Mobile:**
- The top nav becomes a **bottom tab bar** with 5 slots: Overview, Products, Competitors, Strategy and Studio ✦. Customers moves into Strategy's tabs.
- The ask bar becomes a sticky pill above the tab bar.
- Charts scroll horizontally with snap. The hero bars show the top 5.
- Date controls collapse into one chip that opens a bottom sheet.

**Motion** (the `motion` library; everything respects `prefers-reduced-motion`):

| Element | Behaviour |
|---|---|
| Bars | grow from the baseline with a stagger of 40 ms each; the selected bar's fill morphs from hatched to solid |
| Big numbers | count up over 600 ms |
| Cards | fade and rise 8px, staggered on first view |
| Nav pill | the active indicator slides between tabs (shared layout) |
| Tooltips | spring in near the cursor |
| Insight carousel | story-style progress fill |
| Route changes | cross-fade in under 200 ms (View Transitions where supported) |
| Job progress | animated stage list |

Motion is functional, not decorative. It shows where data came from (bars grow) and what changed (number deltas).

**Charts** are custom SVG components (hatched step bars, dot matrix, step line, radar), because charting libraries fight this look. They are accessible: `<title>`/`<desc>`, a data table fallback, and keyboard focus on bars.

---

## 7. PWA and walkthrough

**PWA**, following Next 16's built-in guidance (check `node_modules/next/dist/docs` for the manifest file convention):
- `app/manifest` with name "Dot & Key Market Studio", `display: standalone`, `theme_color #1A1A1A`, `background_color #EDEDED`, and icons at 192, 512 and maskable sizes.
- A hand-written `public/sw.js`, with no plugin, to avoid Next 16 compatibility risk:

  | Content | Strategy |
  |---|---|
  | App shell and static assets | precache |
  | GET insight, catalog and run JSON | stale-while-revalidate |
  | Images | cache-first, with a size cap |
  | POST jobs | network-only, with an offline toast |

- **Offline:** the last-viewed category and the run outputs stay browsable, behind an "Offline · showing data from 21 Nov" banner.
- **Install prompt:** a custom "Install app" chip after the second visit. iOS gets an "Add to Home Screen" hint.
- **HTTPS is required** in production (§9).

**Walkthrough:**
1. **Welcome sheet** on first run. In 3 swipeable cards it explains what the app does (research → insights → content), with a "Take the 60-second tour" or "Skip" choice.
2. **Spotlight tour** with 7 steps (driver.js, MIT licence, small): category switcher → Opportunity bars → Ask bar → Insight card's "Create content" → Products → Strategy → Studio stepper.
   - It shows a progress dots row, which starts at 1/7.
   - Each step is a short sentence plus a "Try it" action.
3. **Contextual coach marks** the first time a screen is opened, e.g. the first Studio visit asks you to paste a reel link.
4. "Replay tour" sits in the help menu. Completion state is stored in `localStorage`, wrapped in try/catch.
5. A **demo mode** preloads the Sunscreen category and the `watermelon-demo` Studio run, so any judge can click through without keys or waiting.

---

## 8. Backend changes to make it one product

| Add | Why |
|---|---|
| `/api/overview?category&as_of&compare` | One slim payload for the home screen. Today's insight JSON is 1 MB per category, which is too slow for the Doherty threshold. |
| Precomputed insight cache (`data/cache/insights/{cat}-{as_of}.json`), rebuilt nightly and after crawls | Every GET under 100 ms |
| `/api/products`, `/api/products/{handle}` | Products screen: listings, snapshots, reviews |
| `/api/competitors?category`, `/api/launches` | Competitors screen |
| `/api/ask` (streaming) | Grounded Q&A for the ask bar, with citations to card IDs |
| `/api/jobs/{id}/events` (SSE) | Live progress for crawls and Studio jobs. Replaces polling. |
| `/api/refresh?category` | "Refresh data" button: runs the crawl as a background job |
| `/api/health` and `/api/version` | Deploy health checks |
| **No access gate, no payment steps** (decision on 21 Nov) | Every feature, including paid generation (images, video, VO, LLM), is open to anyone with the URL. There is no login, no access code and no "confirm price" dialog. ClipForge's price-confirmation step is auto-confirmed server-side. Cost appears only as small informational text in each artifact's Recipe pane. |
| Invisible backstops (not visible to judges) | (a) Set a **credit limit on the OpenRouter key** in the OpenRouter dashboard; it is currently unlimited. (b) A generous per-IP throttle on generation endpoints only (e.g. 60 per hour), purely against bots. (c) Dedupe identical generation requests via the cache. |
| Single API prefix | Next rewrites `/api/*` → FastAPI, so the browser sees one origin and needs no CORS |

---

## 9. Deployment on Railway

**Decision (21 Nov):** deploy on Railway, using the **Railway CLI session already logged in on this Mac** (`~/.railway/config.json`, shared with the Tribe and CrossTalk projects). Run it with `npx @railway/cli`, which refreshes the session automatically. Verified: logged in, with existing projects `crosstalk` and `radiant-caring`. No token is copied into this repo. There is no domain yet, so we use the Railway-provided `*.up.railway.app` URL, which comes with HTTPS and is enough for the PWA.

**New Railway project `dotandkey-market-studio`** (environment `production`) with 4 services:

```
 browser / PWA ──HTTPS──► web  (public: <name>.up.railway.app)
                           Next.js standalone · studio-web/Dockerfile · listens on $PORT
                           rewrites /api/* and /studio-api/* → http://api.railway.internal:8000
                                        │ private network
                                        ▼
                          api  (private only) · Dockerfile.api at repo root
                           python:3.12-slim + ffmpeg + spaCy model + pinned MiniLM
                           uvicorn --host :: --port 8000      ← "::" required for Railway private networking
                           Volume → /app/data  (SQLite WAL, data/studio/runs, cache)
                                        │ private network
                                        ▼
                     clipforge  (private only) · pinned image or GitHub build at commit bded6ce…
                           HOSTNAME=:: · Volume → /data · LLM/TTS/image/video → api compat shim

                          cron  (Railway cron "45 21 * * *" UTC = 03:15 IST)
                           tiny curl image → POST http://api.railway.internal:8000/api/jobs/nightly
                           (catalog-snapshot, then insight-cache rebuild; runs inside api because volumes are per-service)
```

**Railway-specific gotchas handled:**
- **The volume shadows the image's data.** The committed SQLite files (`data/market-intel.sqlite3` and `competitor-catalogs.sqlite3`, about 16 MB) are copied into the image at `/app/seed-data`. On boot, the api copies them to `/app/data` **only if the volume is empty**. Demo runs (`watermelon-demo`) are seeded the same way.
- **One volume per service:** only api writes to the data volume. The cron service never touches it, and calls api instead.
- **Private networking:** api and ClipForge bind to `::`. The web app uses `api.railway.internal`, and only web gets a public domain.
- **`$PORT`:** web reads Railway's injected `PORT`. api and ClipForge get explicit `PORT=8000` and `PORT=3000` so their internal URLs are stable.
- **Health checks:** api `/api/health`, web `/`. Restart policy is ON_FAILURE.
- **Generated media growth:** runs older than 14 days are pruned nightly, except pinned demo runs.
- **Long jobs:** they run in the api's background workers with SSE progress, so no HTTP request outlives Railway's proxy timeout.

**Config:** keys are set as Railway variables from the local `.env`, without printing them: `railway variables --set …` for `CRUSTDATA_API_KEY`, `OPENROUTER_API_KEY`, `SARVAM_API_KEY`, `SCRAPECREATORS_API_KEY` and `YOUTUBE_API_KEY`. Internal URLs use Railway reference variables, e.g. `STUDIO_BACKEND=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000`.

**Deploy flow:**
1. **Now:** `npx @railway/cli up --service <svc>` from this Mac, per service. This needs the uncommitted Studio work committed first.
2. **Then:**
   - Connect the GitHub repo for auto-deploy on `main`, with **watch paths**: `studio-web/**` → web; `market_intel/**`, `requirements*.txt`, `Dockerfile.api`, `data/*.sqlite3` → api.
   - GitHub Actions run ruff and pytest, `next build`, Playwright smoke tests at 390×844 and 1440×900, and Lighthouse (PWA, performance, accessibility ≥ 90) before merge.

**Local dev parity:** `compose.yaml` at the repo root runs the same 3 containers (web, api, clipforge) with the same env names.

---

## 10. Build order

| # | Step | Done when |
|---|---|---|
| 0 | **Sync with the teammate** on uncommitted Studio work, commit it, then branch `feat/frontend` | Clean tree, no overwrites |
| 1 | Design tokens, Poppins and logo, app shell (frame, pill nav, bottom tab bar), routing for the 6 screens, skeletons | Matches the reference at 1440 and 390 widths |
| 2 | Chart kit: hatched step bars, dot matrix, step line, progress rows, value pills, gradient insight card, with motion | Storybook-style `/dev/kit` page |
| 3 | `/api/overview` and the insight cache, then the Overview screen wired to real data | < 400 ms load on a warm cache |
| 4 | Products, Competitors, Customers and Strategy screens on the existing endpoints plus the new list endpoints | All 10 categories navigable |
| 5 | Port the Studio prototype into the shell: stepper, 4-pane cards, lineage drawer, **"Create content from this"** links from insights, SSE progress | The demo chain works end to end |
| 6 | Ask bar (slash commands, grounded Q&A) | Citations open the right card |
| 7 | Walkthrough, welcome sheet and demo mode | A first-time user completes the tour on a phone |
| 8 | PWA manifest, service worker, offline banner, install prompt | Installable; Lighthouse PWA passes |
| 9 | Dockerfiles (web, api), seed-on-boot, `::` binding, health checks, nightly job endpoint, root `compose.yaml` for local parity | `docker compose up` works locally |
| 10 | Railway project, 4 services, volume, variables, then `railway up`. Then GitHub auto-deploy with watch paths and CI. | The `*.up.railway.app` URL serves the full demo over HTTPS and installs as a PWA |

**Demo path** (mirrors the brief's DEMO section):
1. Overview → pick Sunscreen.
2. Competitors (top 5, launches) → Customers (complaints, strengths) → Strategy (SWOT, gaps, recommendations).
3. "Create content from this" → Studio.
4. Paste a competitor reel to deconstruct it → concept.
5. Static ads, A+ content, listing, script and storyboard, video → test plan → "Campaign kit ready".

---

## 11. Decisions (21 Nov)

1. **Folder name:** keep `studio-web/`. Renaming would collide with the teammate's in-flight edits, and the name doesn't show anywhere user-facing.
2. **Hosting:** Railway, using the existing CLI login on this Mac, with no custom domain (`*.up.railway.app`). See §9.
3. **Brand:** logo, colours and fonts are taken from dotandkey.com (Poppins, `#82B51C`, `#FF40B1`, `#FF803A`, `#22BCE0`, `#1A1A1A`). The logo SVG is fetched from the site header and saved to `studio-web/public/brand/`.
4. **Access:** fully open, with no code, no login and no payment or price-confirmation steps. Judges can use every feature, including paid generation. Only the invisible backstops in §8 remain.
