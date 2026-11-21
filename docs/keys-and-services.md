# Keys and Services

**Rule:** use our three keys (Crustdata, Sarvam, OpenRouter) first, then free or free-trial services, and paid services only when nothing else works. **No key is needed** to browse the included data and the Watermelon demo campaign. Keys only enable new crawls, research and generation.

Prices drift. Check `GET https://openrouter.ai/api/v1/videos/models` and `/api/v1/images/models` before relying on the figures below, which were checked on 21 Nov 2026. The hero-film button quotes the live price itself.

## What each key unlocks

| Key | Without it | With it |
|---|---|---|
| `CRUSTDATA_API_KEY` | Public crawl only: Shopify, Judge.me, direct Amazon and Flipkart pages, news RSS | Marketplace search, batched and browser-like page fetch (needed for Nykaa), company enrich (traffic, hiring, funding, followers), news and AI competitor checks, social post discovery |
| `OPENROUTER_API_KEY` | Ask falls back to lexical top-3. Studio copy, video understanding, images and hero video are unavailable. | Ask evidence selection, Studio concepts, scripts and listings, reel deconstruction, ad backgrounds, hero film, ClipForge script judge, fallback field extraction in Part 1 |
| `SARVAM_API_KEY` | Draft voice-overs use free Edge TTS or espeak. Transcription uses local faster-whisper. No Hindi or Hinglish localization. | Bulbul narration, Saaras transcription (handles code-mixed speech), Mayura and Sarvam-Translate localization with back-translation checks |
| `SCRAPECREATORS_API_KEY` | No Instagram or TikTok account discovery, and pasted Instagram links need the media attached | Instagram and TikTok posts, account baselines and media download. **The free tier is about 100 credits, so ration them.** |
| `YOUTUBE_API_KEY` | No YouTube account discovery (pasted YouTube links still work through yt-dlp) | Shorts and channel stats for outlier scoring (10k units a day, and a search costs 100) |

## Models in use

| Purpose | Model (via OpenRouter unless stated) | Override | Rough cost |
|---|---|---|---|
| Part 1 fallback field extraction | `anthropic/claude-haiku-5.5` | `OPENROUTER_MODEL` | fractions of a cent |
| Ask: choose evidence card IDs (no text is shown) | `openai/gpt-4o-mini` | `MARKET_ASK_MODEL` | fractions of a cent |
| Studio concepts, scripts, listings, A+ copy | `anthropic/claude-sonnet-5.5` | `STUDIO_COPY_MODEL` | cents per asset |
| Reel and post understanding (video input) | `google/gemini-2.5-flash` | `STUDIO_VISION_MODEL` | cents per reel |
| Ad backgrounds and scenes | `bytedance-seed/seedream-4.5` | `STUDIO_IMAGE_MODEL` | about $0.05 per image |
| Hero film motion | `google/veo-3.1-lite` | n/a | about $0.03–0.05/s, so **a 15 s film costs about $0.50–0.75** |
| ClipForge script judge | `google/gemini-2.5-flash-lite` | `STUDIO_JUDGE_MODEL` | fractions of a cent |
| Narration | Sarvam `bulbul:v3` | n/a | about ₹30 per 10k chars |
| Transcription | Sarvam `saaras:v3` (local faster-whisper as fallback) | `STUDIO_WHISPER_MODEL` (local weights path) | about ₹30 per audio hour |
| Translation | Sarvam `mayura:v1` forward, `sarvam-translate:v1` back | n/a | small |

**Demo budget:** about $5–10 in total covers 30 images, 2–3 short films, LLM calls and 20 reel breakdowns.

## Free services and local tools
| Service | Use |
|---|---|
| Shopify `/products.json` (D&K plus 9 competitors) | Catalogs, prices, daily launch and price-change detection (polite at 1 req/s) |
| Judge.me widget | D&K on-site reviews |
| Google News RSS, indexed Reddit | Launch news and customer discussions |
| yt-dlp | Download YouTube (and some public) videos for deconstruction |
| D&K's own Shopify images | Packshots for ad cut-outs and draft-film B-roll. **Pexels is not available to us.** |
| Edge TTS, espeak | Free draft voice-overs |
| spaCy, MiniLM ONNX, rembg (U2NetP), OpenCV, Tesseract (English and Hindi), ffmpeg, Chromium through Playwright | Sentence splitting, request clustering, packshot cut-outs, frame analysis, OCR, video processing, HTML-to-PNG ad rendering |

## Dropped (paid alternatives we don't need)
| Dropped | Replaced by |
|---|---|
| Anthropic direct | OpenRouter (Anthropic direct is still used as a fallback if only `ANTHROPIC_API_KEY` is set) |
| Atlas Cloud (ClipForge's default gateway) | OpenRouter through the compat shim |
| Virlo | Crustdata social search, YouTube API, ScrapeCreators free tier and the paste-link flow |
| Firecrawl | Shopify JSON and Crustdata fetch |
| MiniMax or OpenAI TTS | Sarvam Bulbul, or Edge TTS |
| Pexels | D&K Shopify images |

## How ClipForge uses our keys (unmodified)
ClipForge's "OpenAI-compatible" media providers point at our **compat shim** (`market_intel/studio_film/shim.py`), which translates:
- `/v1/audio/speech` → Sarvam Bulbul
- `/v1/images/generations` and `/v1/images/edits` → OpenRouter images
- `/v1/videos` → OpenRouter videos (submit, poll, download)

The shim requires `STUDIO_SHIM_TOKEN`. See [architecture.md §6](architecture.md#6-clipforge-integration).

## Environment variables

Copy `.env.example` to `.env`. It is git-ignored, so never commit it.

| Variable | Default | Purpose |
|---|---|---|
| `CRUSTDATA_API_KEY`, `OPENROUTER_API_KEY`, `SARVAM_API_KEY`, `SCRAPECREATORS_API_KEY`, `YOUTUBE_API_KEY` | none | Provider keys (see above) |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | none | Direct Anthropic fallback for Part 1 extraction |
| `OPENROUTER_MODEL`, `MARKET_ASK_MODEL`, `STUDIO_COPY_MODEL`, `STUDIO_VISION_MODEL`, `STUDIO_IMAGE_MODEL`, `STUDIO_JUDGE_MODEL` | see the models table | Model overrides |
| `MARKET_INTEL_DB` | `data/market-intel.sqlite3` | Part 1 database |
| `COMPETITOR_CATALOG_DB` | `data/competitor-catalogs.sqlite3` | Daily competitor catalog snapshots |
| `MARKET_INSIGHT_CACHE` | `data/cache/insights` | Versioned insight reports |
| `MARKET_COLLECTION_TIMEOUT_SECONDS` | `7200` | Deadline for a refresh or nightly run |
| `MARKET_INTEL_MINILM_PATH` | `data/models/all-MiniLM-L6-v2` | Local embedding weights |
| `STUDIO_RUNS_DIR` | `data/studio/runs` | Campaign run folders |
| `STUDIO_RESEARCH_CACHE` | `data/cache/studio-research` | Cached social API responses |
| `CLIPFORGE_URL` | `http://127.0.0.1:3039` | ClipForge sidecar (`http://clipforge:3000` in Compose) |
| `STUDIO_SHIM_TOKEN` | none | Bearer token for the ClipForge media shim |
| `STUDIO_GRID_BIND_HOST`, `STUDIO_GRID_CALLBACK_HOST` | `127.0.0.1` | Where the per-operation callback listens, and how ClipForge reaches it |
| `STUDIO_PUBLIC_ORIGIN` | none | The public web origin allowed to change campaigns. Studio writes are refused from any other `Origin` except localhost:3000. |
| `STUDIO_TRUST_PROXY` | unset | Set to `1` behind Railway to throttle by `X-Real-IP` |
| `STUDIO_CHROME_BIN`, `FFMPEG_PATH`, `STUDIO_WHISPER_MODEL` | auto | Local tool locations |
| `JOBS_CRON_TOKEN` | none | Bearer token for `POST /api/jobs/nightly` |
| `STUDIO_BACKEND` (web) | `http://127.0.0.1:8000` | Where Next proxies `/api` and `/studio-api` |
| `PORT` | `8000` | API port |
| `RAILWAY_WORKSPACE` | none | Workspace for `deploy/railway.py` |
| `STUDIO_TEST_ORIGIN`, `STUDIO_TEST_CHROME`, `STUDIO_TEST_RESULTS` | localhost | Smoke and Lighthouse checks |
