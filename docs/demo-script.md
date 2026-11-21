# Live Demo Script (about 8 minutes)

Every Ask question below was run through the real `/api/ask` pipeline on 21 Nov 2026, and the quoted answers are what came back. Ask doesn't write free text. It picks evidence cards from the data and quotes them with numbered sources, so every answer can be traced to a review, a listing or a catalog entry.

Open the command bar with **⌘K** (or Ctrl+K). It has two tabs. **Search** jumps anywhere, and anything starting with `/` is a jump. **Ask the market** answers questions about the category that is currently selected.

## 0. Before the reps arrive
- Open the app and pick **Sunscreen**.
- Press **Refresh data** now. The Crustdata re-crawl runs in the background, and you reveal the fresh `as of` timestamp at the end.
- Have two tabs ready: the Studio run **Watermelon Sunscreen** (`watermelon-demo`), and one Instagram reel or YouTube Short link copied to the clipboard.

## 1. Hook: "Where should Dot & Key spend next?" (Overview)
Point at the Category Opportunity bars: **Lip Balm 0.70 · Body 0.58 · Sunscreen 0.40 · Moisturiser 0.40**.

| Type | Answer you'll get |
|---|---|
| `/lip balm` (Search) | jumps to the Lip Balm category |
| **Ask:** `What is our review share?` | "Dot & Key accounts for **19.8%** of observed lip balm review volume" (vs **67.8%** in Sunscreen) |
| **Ask:** `Who are our top competitors in lip balm?` | Chemist at Play, WishCare, Deconstruct, ranked, with links |
| **Ask:** `What should we do in lip balm?` | Foxtale has 3 recent lip balm launches, plus Minimalist and Mamaearth |

> Line: "Lip Balm is where you're under-indexed, and Foxtale is moving in right now."

## 2. Market intelligence (Sunscreen, the hero category)
Type `/sunscreen`, then use Ask:

| Ask | Answer |
|---|---|
| `What do customers complain about?` | Greasy/sticky in 182 reviews (12 negative) · White cast in 72 (10 negative) · Irritation in 26 (6 negative) |
| `What are the threats?` | Foxtale has 4 recent sunscreen launches · DermDoc scores higher at a comparable or lower price per g · Deconstruct launch |
| `Who beats us on price per gram?` | DermDoc, plus the action "Benchmark the comparable pack against DermDoc before the next price test" |
| `Which of our sunscreens rates lower on Amazon?` | Vitamin C + E Mineral Sunscreen SPF 50+, plus "Audit the Amazon listing… compare with Flipkart" |
| `What are the biggest gaps?` | **Mist · SPF 50 · under ₹500: 0 products.** Stick and tinted at the same spec: 0 products |
| `Who launched new sunscreens recently?` | Foxtale Tinted Fluid (14 Oct) · Re'equil UV Mini (12 Oct) · Deconstruct Gel (9 Oct) |
| `How does demand look for the next 3 months?` | +30.9% projected growth in review activity |
| `What are our strengths?` | Dot & Key ranks 2 of 6 on Bayesian rating |

**Click a numbered source** in any answer. It opens the exact card, with the review quotes and marketplace URL behind it. That's the trust moment.

Then use Search: `/swot` to open the full SWOT, and `/competitors` to open the top 5 with prices, ratings and launches.

> Line: "No one wrote these insights. Rules over scraped reviews and catalogs produced them, so they cost no AI and they're the same every time you run them."

## 3. From insight to content (Studio)
1. On the **mist · SPF 50 · under ₹500** gap card, click **Create content from this →**. The campaign brief opens with that evidence attached.
2. Search `/product watermelon` to show the hero SKU.
3. **Research → Paste link:** paste the reel URL you copied. *(Live; it takes a little while and uses one ScrapeCreators credit for Instagram. Fallback: one of the four reels already broken down, such as `instagram.com/reel/DY1Ln6bzPh7`, outlier ×168.)*
4. **Deconstruct:** walk through the hook timing, beats and on-screen text.
5. **Patterns:** "Show the demonstration early". The hook is under 1.5 s and the product appears by 3 s.
6. **Concepts → Create:** tab through **Statics** (Meta, Amazon, Flipkart and Nykaa banners), **A+ content**, **Listing**, **Script & storyboard** and **Video** (the pre-rendered hero film, with Reels, Shorts and Meta exports).
7. **Listing → Localize → Hindi** (Sarvam). *(Live, fast, costs a few paise.)*
8. **Test:** show the QC gate (claim guard: exact catalog wording and SPF = pass), then download the campaign kit .zip.

## 4. Close (peak-end)
Go back to Overview and show the refreshed `as of` timestamp from step 0.

> Line: "Catalog to competitors to sentiment to SWOT to a finished, checked campaign. Your team can run this nightly."

## Don't do these live
| Avoid | Why |
|---|---|
| Generating a **new video** | Takes minutes and costs about $0.50–0.75. Show the pre-rendered film. |
| "Why…" or open-ended trend questions, such as `Is no white cast still a trend?` | Returns "insufficient evidence". Ask is built to refuse rather than guess, so it's a good answer to give if a rep tries it. |
| `Which competitor offers better value?` | Returns the competitor list. Use `Who beats us on price per gram?` instead. |
| `Why is lip balm our biggest opportunity?` | Returns only the bare score. Use the review share and competitor questions instead. |

## If a rep asks their own question
Steer it toward a topic Ask can answer from evidence:
- complaints
- gaps or whitespace
- launches
- competitors
- threats, weaknesses or strengths
- review share
- demand or forecast
- what we should do

These work in any category, e.g. Moisturiser → `What do customers complain about?` (greasy/sticky, breakouts, irritation) or `What new launches should we worry about?` (Plum CeraSense, Mamaearth Rice Dewy, TDC Nia-Ceramide).
