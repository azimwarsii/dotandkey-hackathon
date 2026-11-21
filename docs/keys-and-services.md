# Keys and Services: Parts 1–3

**Rule:** use our three keys (Crustdata, Sarvam, OpenRouter) first, then free or free-trial services, and paid services only when nothing else works. Model and price facts were checked on 21 Nov 2026. Prices drift, so call `GET https://openrouter.ai/api/v1/videos/models` and `/api/v1/images/models` before relying on them.

## Our keys

### Crustdata (`CRUSTDATA_API_KEY`)
| Part | Use |
|---|---|
| 1 | `/web/search/live` to find marketplace listings (`site:amazon.in`, `flipkart.com`, `nykaa.com`). `/web/enrich/live` to fetch listing and review pages (`human_mode` for Nykaa). |
| 1–2 | `/company/enrich` for competitor brand signals: traffic, followers, headcount, hiring, funding, news, SEO competitors |
| 2 | `news` source with `start_date` for launch and trend news |
| 3 | `social` source or `site:instagram.com/reel` / `youtube.com/shorts` to **discover** winning posts (URLs only; ScrapeCreators or yt-dlp fetch them) |

Budget is about 750 credits for a full Part 1 crawl, plus a little for Part 3 discovery. Rate limit is 10 RPM on web search and fetch.

### OpenRouter (`OPENROUTER_API_KEY`)
| Use | Endpoint and model | Rough cost |
|---|---|---|
| Final copy, scripts, concepts, A+ text | Chat completions: Claude Sonnet | cents per asset |
| Bulk and cheap work: parser fallback, attribute fill, judges | Gemini Flash or Claude Haiku. `:free` models only for non-critical batch work, since they are rate-limited. | fractions of a cent |
| Video and post breakdown | Gemini Flash with `video_url` (base64 mp4). This is the breakout kit's own path. | cents per reel |
| Ad backgrounds and scenes with the product as reference | `POST /api/v1/images` with `input_references`: `bytedance-seed/seedream-4.5` (about $0.05) or `google/gemini-2.5-flash-image` | about $0.05 per image |
| Ad film shots | `POST /api/v1/videos`, then poll `GET /api/v1/videos/{id}`, then download `/content?index=0`. `google/veo-3.1-lite` costs about $0.03/s at 720p without audio and about $0.05/s with audio. `bytedance/seedance-2.0-mini` is also cheap. Image-to-video uses `frame_images` (first and last frame). | **a 15 s film is about $0.50–0.75** |

**Demo budget estimate:** about $5–10 in total: 30 images, 2–3 short films, LLM calls and 20 reel breakdowns.

### Sarvam (`SARVAM_API_KEY`)
| Use | Model | Cost |
|---|---|---|
| Voice-over for ads in Hindi, Hinglish, Indian English or regional languages | Bulbul (v3 or newer) | about ₹30 per 10k characters, so a 30 s VO costs about ₹1.5 |
| Reel transcription, which handles code-mixed speech | Saaras | about ₹30 per audio hour |
| Hindi and regional variants of listings, captions and scripts | Sarvam translate | small |

Free credits on signup are ₹100–1,000; the pages disagree, so check the dashboard. That is plenty for a demo.

## Free and free-trial services
| Service | Use | Limit |
|---|---|---|
| Shopify `/products.json` (D&K plus 9 competitors) | Catalogs, prices, launch detection | Be polite: 1 req/s |
| Judge.me widget | D&K on-site reviews | — |
| ScrapeCreators | Instagram and TikTok post and profile fetch, and competitor-account outliers | About 100 free credits plus claimable extras. **Save them for Instagram.** |
| YouTube Data API v3 | Shorts search and stats | 10k units a day (search costs 100 units) |
| yt-dlp | Download YouTube (and some public Instagram) videos for breakdown | — |
| **D&K's own Shopify images** (primary B-roll) | 712 official images across 66 single SKUs (median 8 per product, including lifestyle, texture and model shots), loaded into the ClipForge local material library. On-brand and free. | — |
| ClipForge keyless stock (Openverse, Wikimedia, Internet Archive) | Generic B-roll fallback; works with no key | — |
| Pixabay (optional) | Extra stock video, from an instant free signup. **Pexels is not available to us.** | Free key |
| Edge TTS (built into ClipForge) | Free draft voice-overs (en-IN, hi-IN) | — |
| Local tools: ffmpeg, faster-whisper, PaddleOCR or Tesseract, rembg, OpenCV, Playwright, spaCy, statsmodels | Cuts, frames, fallback STT, OCR, product cut-outs, rendering, NLP, forecasting | — |

## Dropped (paid alternatives we don't need)
| Dropped | Replaced by |
|---|---|
| Anthropic direct | OpenRouter |
| Atlas Cloud (ClipForge's default model gateway) | OpenRouter through the compat shim |
| Virlo | Crustdata social search, YouTube API, ScrapeCreators free tier and the paste-link flow |
| Firecrawl | Shopify JSON and Crustdata fetch |
| MiniMax or OpenAI TTS | Sarvam Bulbul, or Edge TTS |

## How ClipForge uses our keys (unmodified)
- **LLM:** set to OpenRouter (`https://openrouter.ai/api/v1`), which is a built-in preset.
- **TTS, image and video:** point ClipForge's "OpenAI-compatible" providers at our **compat shim**, which translates:
  - `/audio/speech` → Sarvam Bulbul
  - `/images/generations` and `/images/edits` → OpenRouter `/api/v1/images`
  - `/videos` → OpenRouter `/api/v1/videos`, with status and download mapping
- **Fallback:** generate the clips and images ourselves, then upload them into ClipForge's local material library and compose there.

## `.env`
```
CRUSTDATA_API_KEY=          # verified 21 Nov: 4,621 credits
OPENROUTER_API_KEY=         # verified: paid key, no limit set
SARVAM_API_KEY=             # verified (translate call OK)
SCRAPECREATORS_API_KEY=     # verified: 100 free credits, so ration them for Instagram
YOUTUBE_API_KEY=            # verified
PIXABAY_API_KEY=            # optional, free
```
