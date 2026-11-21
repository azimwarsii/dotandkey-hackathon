# Run Market Studio

How the pieces fit together under the hood is described in [architecture.md](architecture.md). The live demo script is in [demo-script.md](demo-script.md).

From the repository root, start the same web, API and ClipForge containers used in production. The first build downloads the media tools and pinned inference models.

```sh
docker compose up --build -d
```

Open [Market Studio on localhost](http://localhost:3000). The Sunscreen dashboard and Watermelon campaign kit use the committed data and work without provider keys. The local web port binds to loopback. To configure new research or generation, populate the ignored root `.env` using `.env.example` and run `docker compose up -d` again.

The API copies both SQLite databases and the demo into a fresh volume at startup. A restart resumes an interrupted copy. Subsequent starts preserve stored research and runs. ClipForge stores its editing projects in a separate volume. `docker compose down` stops both writers and retains their volumes.

## Railway

Use Node 22, Git and the project's Python environment with `python-dotenv` installed. Sign in to Railway's CLI in the intended account. The deployment script uses the current commit and builds ClipForge from upstream revision `bded6ceaa46649068e8da5882d7c29fd8c977a3b`.

```sh
.venv/bin/python deploy/railway.py
```

The command selects or creates the exact project `dotandkey-market-studio` in the selected workspace. If you belong to several workspaces, set `RAILWAY_WORKSPACE` to its name or ID. Capacity for four services and two persistent volumes is required. The script waits for deployment results, verifies the demo, health, manifest and service worker over HTTPS and prints the web URL.

| Service | Exposure | Storage and operation |
| --- | --- | --- |
| web | Public Railway HTTPS domain | Next standalone proxies the public market and Studio routes to the API. |
| api | Private, port 8000 | `/app/data` holds market databases, cached insights, job receipts and Studio runs. Railway supplies the visitor IP in `X-Real-IP`. |
| clipforge | Private, port 3000 | `/data` holds the upstream project database and media. The API creates a token-protected callback for each media operation. |
| cron | Private, scheduled | At 03:15 IST (`45 21 * * *` UTC), posts a bearer-authenticated nightly job to the API. The job takes catalog snapshots, warms the insight cache and prunes unpinned runs older than 14 days. |

The script transfers configured research and media provider keys to the API through stdin. It verifies the OpenRouter key's credit limit with OpenRouter before enabling public paid generation. If a capped key is unavailable, the deployed demo and deterministic tools remain available. Once the limit has been set, rerun the command. [OpenRouter key information](https://openrouter.ai/docs/api/api-reference/api-keys/get-current-key)

After merging the tested revision into the GitHub `main` branch, run the following command from that revision to connect Railway's GitHub integration. Railway must have access to `azimwarsii/dotandkey-hackathon`. The command configures separate watch paths for the frontend, API and cron sources.

```sh
.venv/bin/python deploy/railway.py --connect-main
```

## Verification

GitHub Actions starts the three-container stack, runs Ruff and pytest, exercises the dashboard and offline campaign kit at 390 × 844 and 1440 × 900, and audits the production web origin three times in sequence with Lighthouse’s default simulated mobile throttling. The median performance and accessibility scores must each reach 90. Playwright checks the PWA manifest, icons, active service worker and offline navigation. The workflow attaches screenshots, all three Lighthouse reports, Chrome traces and network logs, a runner resource snapshot, and the median scores.

With the stack running locally, run the browser checks directly. `STUDIO_TEST_ORIGIN` selects another origin and `STUDIO_TEST_CHROME` can point to an existing Chromium executable.

```sh
.venv/bin/python -m playwright install chromium
.venv/bin/python deploy/smoke.py
python3 deploy/audit_web.py
```
