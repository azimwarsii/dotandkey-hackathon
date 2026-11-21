# Demo video: plan and script (1:53)

Final cut: `~/Movies/market-studio-demo/market-studio-demo.mp4` (1080p, 30 fps, -16 LUFS), with captions in `market-studio-demo.srt`.

It's recorded from the real app running locally (web on :3100, API on :8000). Nothing is mocked. Three actions run live on camera: the **Ask** answer, the **campaign brief created from a market gap**, and the **Hindi translation** through Sarvam. Each one has a "Live" badge.

The story follows the brief's DEMO box in order. One category (Sunscreen) is analysed: competitors, customer insights, market gaps and recommendations. The same product (Watermelon Sunscreen) is then turned into static ads, e-commerce content, an ad script and a promotional video.

## Shot list

| Time | Chapter | On screen | Voiceover |
|---|---|---|---|
| 0:00 | Title | Title card, then the app's welcome sheet, then Skip | Dot and Key sells in ten categories, on its own store and three marketplaces. Market Studio turns that market data into a finished, checked campaign. |
| 0:10 | 01 Market overview & forecast | Lip Balm: opportunity 0.695 (rank 1), demand index +21.7% with forecast. Switch the category to Sunscreen (5.6% review share). | It crawls the catalogue, Amazon, Flipkart and Nykaa, and scores every category. Lip balm leads, with demand forecast up twenty-two percent. Let's take sunscreen. |
| 0:22 | 02 Competitor comparison | Top 5 with price and rating, aspect radar, competitor launches | It finds the top five competitors with prices and ratings, compares them aspect by aspect, and tracks their new launches. |
| 0:29 | 03 Customer sentiment | 995 reviews, aspect cards. Open "Why?" on white cast and zoom in on the real review quotes. | Sentiment across nearly a thousand reviews shows what buyers care about: greasiness, texture and white cast, each linked to the reviews behind it. |
| 0:38 | 04 Ask the market · **Live** | Type "Who scores higher at a lower price?". The answer appears with sources [1][2][3], zoomed in. | Or just ask. Who scores higher at a lower price? The answer is built from evidence, not a chatbot, so every line cites its source. |
| 0:48 | 05 SWOT, gaps & recommendations · **Live** | SWOT, then Gaps ("mist · SPF 50 · under ₹500 has 0 observed products"), then Recommendations. Create content from this, pick Watermelon Sunscreen, and the brief starts building. | Strategy builds the SWOT, spots gaps, like no SPF fifty mist under five hundred rupees, and recommends next moves. One click turns any insight into a campaign brief. |
| 1:00 | 06 Studio · reel research | Finished Watermelon campaign: brief, then References (168.6× baseline reel), then Breakdown (hook frames) | Here's a finished Watermelon Sunscreen campaign. The studio finds reels that beat their usual views, this one a hundred and sixty-eight times over, and breaks down the hook and timing. |
| 1:10 | 07 Ad script & storyboard | Patterns, then Concepts, then the script table with an Evidence column, then the storyboard grid | That winning pattern becomes a concept, then a shot-by-shot script and storyboard, with every line traced back to catalogue wording. |
| 1:18 | 08 Static ads, A+ & listings · **Live** | Ads grid, A+ modules, marketplace listings, then Generate translation to Hindi (sped up 8×), zoomed in | Then static ads for Meta, Google and every marketplace, A-plus content, listings, and a Hindi translation, generated live. |
| 1:29 | 09 Promotional video | The hero film plays in the screening room. Its own Sarvam narration comes up after the voiceover ends. | And a hero film with an AI voiceover, checked automatically against the brief. |
| 1:39 | 10 Claim guard, tests & kit | Pre-flight ("passed claim guard"), then the variant matrix and first three A/B tests, then the campaign kit and Download kit | A claim guard blocks anything the catalogue doesn't say. Then it plans the A B tests, and packages the kit. |
| 1:47 | Close | End card with the full chain | Market Studio. From market intelligence to marketing content, in one app. |

Speed-ups: screen actions run at 1.1–2.2× to fit each line, and the translation wait runs at 8×. The badge says so.

## Before you submit
- **YouTube unlisted** is the safest choice. Studio → Upload → Visibility: **Unlisted**. Under Subtitles, upload `market-studio-demo.srt` so mentors watching muted still follow.
- If you use Google Drive, set Share → General access to **Anyone with the link** (Viewer). Drive can take a few minutes to process a 32 MB video before it plays.
- **Test the link in a private or incognito window while logged out.** A link the mentor can't open counts as no video.
- Check the length: 1:53, which is under the 2:00 limit.

## Re-rendering (for example, with your own voice)
Your own voice usually lands better with judges than a synthetic one. The timings are fixed by each scene, so you can record the lines in the table above one by one as `vo/<scene>.wav`. Keep each line close to the length of the generated one, then rerun `edit.py`.

```sh
cd demo-video
../.venv/bin/python tts.py                      # regenerate the voiceover from vo.json (edge-tts)
../.venv/bin/python record.py                   # re-record every scene (needs web on :3100 and API on :8000)
../.venv/bin/python record.py s05_ask s09_ads   # or only some scenes
../.venv/bin/python render_cards.py
mkdir -p out && ../.venv/bin/python edit.py out/market-studio-demo.mp4
```

Notes:
- `record.py` clicks **Create campaign brief** and **Generate translation** for real. That creates a new Studio run under `data/studio/runs/` and a Hindi locale file, so delete them afterwards if you want a clean tree.
- The translation button only appears when the campaign has no Hindi locale yet.
- Recording uses installed Google Chrome, because Playwright's Chromium can't play the H.264 film.
