# Live Demo Script (about 8 minutes)

Every question below was run through the real `/api/ask` pipeline on 21 Nov 2026. The answers are summarised from what came back. **The exact figures change whenever the data is re-crawled**, so run through the questions once on the deployed app before the demo.

Ask doesn't write free text. It picks up to three evidence cards from the data and quotes them with numbered sources, so every answer can be traced to a review, a listing or a catalog entry. That is the pitch: *it can't make things up*. See [architecture.md §4](architecture.md#how-ask-answers-a-question).

## How the box works
Press **⌘K** (Ctrl+K), or click the search pill.
- **A question** (starting with *what, who, how, which, why…* or ending in `?`) → Enter **answers** it for the current category.
- **Anything else** (a product, category, campaign or view) → Enter **jumps** to the top result.
- `/` at the start always jumps: `/lip balm`, `/sunscreen`, `/competitors`, `/swot`, `/product watermelon`, `/campaign kit`, `/video production`.
- Click a numbered source under an answer to open the exact card behind it.

## 0. Before the reps arrive
- Open the app.
- Press **Refresh data** on one category. The re-crawl runs in the background with live stage names, and you reveal the fresh `as of` date at the end.
- Copy one Instagram reel or YouTube Short link to the clipboard.
- **Use a different network (or phone hotspot) for the rehearsal than for the demo.** Every Ask, Refresh and Studio action counts toward a hidden limit of 60 per hour per IP.

## 1. Hook: "Where should Dot & Key spend next?" (Overview)
Point at the **Category opportunity** bars. Lip Balm leads (0.70), then Body (0.58).

| Type | What comes back |
|---|---|
| `/lip balm` | jumps to the Lip Balm category |
| `Why is lip balm our biggest opportunity?` | the score and its parts: **+21.7% projected growth, only 19.8% D&K review share, 4 distinct market gaps**, plus the gaps themselves (tinted lip balm for sensitive and oily skin: 0 products) |
| `Who are our top competitors in lip balm?` | Chemist at Play, WishCare, Deconstruct, with median price and rating |
| `Who launched new lip balms recently?` | Foxtale Pout Plumping Lip Mask (26 Oct), Foxtale Lip Up Plumping Balm (15 Oct), Mamaearth × Chaayos Kulhad Chai (4 Sep) |
| `How does demand look for the next 3 months?` | +21.7% projected growth in review activity, plus Foxtale's launch push |

> Line: "Lip Balm is growing, you hold under a fifth of the conversation, and Foxtale is launching into it right now."

## 2. Market intelligence (Sunscreen, the most competitive category)
Type `/sunscreen`, then ask:

| Ask | What comes back |
|---|---|
| `What do customers complain about?` | Greasy/sticky (about 190 reviews), white cast (about 75), irritation (about 25), each with its negative count |
| `What are our weaknesses?` | The Vitamin C + E Mineral Sunscreen rates lower on Amazon, plus white cast and greasiness |
| `Which of our sunscreens rates lower on Amazon?` | That SKU, with the action "Audit the Amazon listing… compare with Flipkart" |
| `What are the threats?` | Foxtale has 4 recent sunscreen launches, then Deconstruct and Re'equil launches |
| `Who scores higher at a lower price?` | **Foxtale scores higher at a comparable or lower price per ml**, plus "Benchmark the comparable pack against Foxtale before the next price test" |
| `What are the biggest gaps?` | SPF 50 lotion at ₹500–999, SPF 50 mist under ₹500 and SPF 50 stick under ₹500: **0 products observed** in each |
| `Who launched new sunscreens recently?` | Foxtale Tinted Fluid (14 Oct), Re'equil UV Mini (12 Oct), Deconstruct Gel (9 Oct) |
| `What are our strengths?` | Dot & Key ranks 2 of 6 on Bayesian rating |
| `What should we do next quarter?` | Audit the Amazon listing, then compare the new Foxtale and Deconstruct listings with the closest D&K variants |

**Click a numbered source.** It opens the exact card with the review quotes and marketplace URLs. This is the moment the reps start to trust it.

Then open `/swot` for the full SWOT and `/competitors` for the top 5 with prices, ratings, launches and the aspect radar.

> Line: "No one wrote these insights. Rules over scraped reviews and catalogs produced them, so they cost no AI and they're the same every time you run them."

## 3. From insight to content (Studio)
1. On the **SPF 50 mist under ₹500** gap card (Strategy → Market gaps), click **Create content from this**. The campaign brief opens with that evidence attached.
2. To show the finished example, open `/campaign kit`, or switch to the **Watermelon Sunscreen** campaign.
3. **Research → paste link:** paste the reel URL from your clipboard. *(This runs live and takes a little while. Instagram uses one ScrapeCreators credit, while YouTube is free through yt-dlp. Fallback: open one of the four reels already broken down, such as `instagram.com/reel/DY1Ln6bzPh7`, which reached 168× its account's median views.)*
4. **Deconstruct:** click through the frames, cuts, on-screen text, transcript, hook timing and beats. Clicking any of them seeks the video.
5. **Patterns:** "Show the demonstration early". The hook is under 1.5 s, the product appears by 3 s and text by 1 s.
6. **Concepts → Create:** tab through:
   - **Statics** (Meta, Amazon, Flipkart, Nykaa, display)
   - **A+ content**
   - **Listing**
   - **Script & storyboard**
   - **Video** (the pre-rendered 16 s hero film with Reels, Shorts and Meta exports)
7. **Listing → Hindi → Localize** with Sarvam. *(This runs live, is fast and costs a few paise.)* Click a line to show the back-translation check.
8. **Test:** show the gate (claim guard against the exact catalog wording and SPF), the variant matrix, then **download the campaign kit**.

## 4. Close (peak-end)
Go back to Overview and show the refreshed `as of` date from step 0.

> Line: "Catalog to competitors to sentiment to SWOT to a finished, checked campaign. Your team can run this every night."

## Don't do these live
| Avoid | Why |
|---|---|
| **Generate hero film** | Takes minutes and costs about $0.50–0.75. Show the pre-rendered film instead. |
| Demand or forecast questions on **Sunscreen** | Sunscreen's latest data doesn't meet the forecast's coverage threshold, so it answers "I couldn't find enough saved evidence". Ask demand questions on Lip Balm, Moisturiser, Body or Mask. |
| `Which competitor offers better value?` | Returns the plain competitor list. Use `Who scores higher at a lower price?` instead. |
| `What do people say about the watermelon sunscreen?` | Too vague. Type `watermelon sunscreen reviews`, or `/product watermelon` and open the product. |
| Running out of the hourly limit | Ask, Refresh and every Studio action count toward 60 per hour per IP. Don't rehearse on the demo network. |

If a rep tries an off-topic question, Ask answers "I couldn't find enough saved evidence…". **Present that as a feature:** the system refuses to guess.

## If a rep asks their own question
Steer it toward a topic Ask can answer from evidence:
- complaints
- weaknesses, threats or strengths
- gaps
- launches
- competitors
- review share
- price or value
- demand (in categories with a forecast)
- what we should do

These work in any category. For example, in Moisturiser:
- `What do customers complain about?` → greasy/sticky, breakouts, irritation
- `What new launches should we worry about?` → Foxtale (7 recent launches), Pilgrim, The Derma Co
- `How does demand look for the next 3 months?` → +16.7%
