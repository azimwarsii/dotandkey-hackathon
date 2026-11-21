# ClipForge sidecar

The Studio uses the unchanged upstream application at revision `bded6ceaa46649068e8da5882d7c29fd8c977a3b` over its local HTTP API. The upstream project ships under AGPL-3.0. [ClipForge source and licence](https://github.com/xixihhhh/clipforge/tree/bded6ceaa46649068e8da5882d7c29fd8c977a3b)

Start it from this checkout with `docker compose -f clipforge/compose.yaml up --build`, or run `clipforge/start-native.sh` on a machine with Node 22 and npm. Both use local port 3039. Set `CLIPFORGE_URL` to select another local port. Install the film renderer with `.venv/bin/pip install -r requirements-studio-film.txt`. Linux users can install eSpeak for offline narration. The macOS fallback uses the system speech engine.

The adapter imports each approved script, uploads the rendered shot materials with the verified catalog product, composes the variant, and retrieves the upstream contact sheet, QC and release gate. When a product site blocks ingestion, the brief supplies its verified title and local product media. The sidecar remains available separately for editing and inspection. The Studio also retains its frame-accurate local master and platform exports. The Reels and Shorts copies are 1080×1920. The Meta feed export is 1080×1350.

### Provider settings

For ClipForge Director tools that use OpenAI-compatible media providers, set a private `STUDIO_SHIM_TOKEN` in the ignored local environment. Start `.venv/bin/uvicorn market_intel.studio_film.shim:app --host 127.0.0.1 --port 8784`. Configure the local provider base as `http://127.0.0.1:8784/v1` and its API key as your shim token. The shim uses the existing server-side `OPENROUTER_API_KEY` and `SARVAM_API_KEY`. With Docker, bind the shim to the container-accessible host interface and use `http://host.docker.internal:8784/v1` from ClipForge.

The image routes accept both JSON generations and multipart reference edits. The video routes accept multipart first frames, translate job statuses, and return the authenticated MP4. The speech route supports English and Hindi Bulbul voices. Configure the ClipForge LLM separately with OpenRouter's chat completions base. The adapter selects a visible English AI disclosure. Commercial asset clearance remains a separate review on the release gate.

Six free drafts use real catalog photography, animated product and creator storyboards, and Edge TTS or a named local fallback. Paid hero generation checks the live per-second Veo rate against the explicitly supplied approval amount, saves two reference frames with the provider job IDs, and reuses those jobs on retry. A missing submission receipt requires reconciliation before another request. Original Sarvam speech is mixed against an original synthesized underscore.

The paid film run extracts a verified frame from each delivered shot and submits the contact board to ClipForge's storyboard-grid API. A short-lived authenticated shim supplies that exact board to the upstream grid splitter. The board and project receipt are stored under `film/director`. For a Docker-hosted ClipForge, set `STUDIO_GRID_BIND_HOST=0.0.0.0` and `STUDIO_GRID_CALLBACK_HOST=host.docker.internal` to allow the local container to fetch the prepared board.
