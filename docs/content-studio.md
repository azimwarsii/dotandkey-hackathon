# Content Studio

The Watermelon Sunscreen campaign is included at `data/studio/runs/watermelon-demo`. Read the stored campaign without provider credentials. Creating new research and media uses the services enabled in the local `.env`. For hosted operation use the private API, spend controls and HTTPS frontend in the [deployment guide](market-studio-deployment.md).

## Open the studio

Start the existing FastAPI service from the repository root.

```sh
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn market_intel.api:app --host 127.0.0.1 --port 8000
```

In another terminal, use Node 22 to start the interface.

```sh
npm --prefix studio-web ci
npm --prefix studio-web run dev -- --hostname 127.0.0.1 --port 3000
```

Open the [campaign dashboard](http://127.0.0.1:3000/?run=watermelon-demo). The Next.js server proxies `/studio-api` to FastAPI. Use `STUDIO_BACKEND` on the Next.js server to select another API address. For a production build, run `npm --prefix studio-web run build` and then `npm --prefix studio-web start -- --hostname 127.0.0.1`.

## Explore the included campaign

1. **Product brief.** Inspect the approved catalog language, linked product images and Shopify source. Category-level review evidence is labelled separately from SKU evidence.
2. **Swipe file and Deconstruct.** Browse 861 discovered posts from five competitor brands and twelve creator accounts. Of these, 98 reached at least three times their account baseline. Four downloaded reels have frame-by-frame breakdowns. Select a frame, timestamped transcript line or semantic finding to seek in the player.
3. **Pattern board and Concept slate.** Inspect the posts behind each format and compare the three creative directions. The selected direction, *Texture on Fingertips*, uses a Deconstruct reel that received 168.6 times its account median. Its reference pattern has one supporting account.
4. **Script, storyboard and video.** Follow each shot to its evidence. Play the six draft variants and the 16-second hero. The hero passed technical QC. ClipForge flagged the opening hook and subtitle density, and the edit cuts more slowly than its 24.75-second reference. Its storyboard uses verified hero frames after a separate image-model request timed out. Reels and Shorts exports measure 1080×1920, and the Meta export measures 1080×1350.
5. **Ads & listings.** Inspect nine static sizes, five Amazon A+ modules and copy for Amazon India, Flipkart and Nykaa. The script and listing views include Hindi and Hinglish drafts. Select a translated line to review the source, backtranslation and claim checks. Both languages require bilingual signoff before publication.
6. **Testing and lineage.** Review the three priority tests, six-variant matrix, and links from claim to frame. A published post can be attached to a variant with observed impressions, three-second views, completions, clicks, spend and acquisitions. Missing denominators produce unavailable rates. The demo has no published post or measured campaign-performance results.

## Create or refresh a campaign

```sh
.venv/bin/pip install -r requirements-studio.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m market_intel.studio_research.whisper_setup
```

The last command installs pinned local transcription weights for the Whisper fallback. A working Chrome installation can also be selected with `STUDIO_CHROME_BIN`. Use Docker Compose or the native launcher for the unmodified ClipForge service and follow its provider-shim instructions. [ClipForge setup](../clipforge/README.md)

Choose **New campaign**, select a Part 1 product and build its brief. Discovery uses available ScrapeCreators, YouTube and Crustdata observations. A pasted public post URL or an uploaded MP4/image carousel can enter the same research pipeline. When a platform blocks retrieval, paste its URL and attach the original media. For a Meta Ad Library screenshot, enter observed campaign dates to calculate running time. Longevity is a proxy for selection, and performance requires actual measurements.

Select a concept and optionally a research reference to match its cuts. Generating a campaign writes its script, listings and artwork into a versioned folder. Draft film composition uses real catalog images and free speech synthesis. **Render hero film** obtains the current motion estimate server-side and records it in the recipe. Audio, image and text services have their own usage. OpenRouter handles creative copy, video understanding, backgrounds and hero motion. Sarvam provides Indian-language transcription and final narration.

All run-owned paths are relative. `STUDIO_RUNS_DIR` selects the storage root. The API returns job IDs for long operations, exposes status via `GET /studio/runs/{id}`, and serializes mutations for each run. A stopped worker is reported as interrupted. Generation receipts permit resuming known paid video jobs. The studio does not publish assets.

## Verification

```sh
.venv/bin/python -m pytest -q
npm --prefix studio-web run build
```

The third-party research scripts and prompt sources retain their upstream licence and pinned revision. [Creator Breakout Kit provenance](../vendor/creator-breakout-kit/UPSTREAM.md)
