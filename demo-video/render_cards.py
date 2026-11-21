import asyncio, json, os
from playwright.async_api import async_playwright
D=os.path.abspath("cards")
CH=[("s02_overview","01","Market overview & forecast"),("s03_competitors","02","Competitor comparison"),
    ("s04_customers","03","Customer sentiment"),("s05_ask","04","Ask the market"),
    ("s06_strategy","05","SWOT, gaps & recommendations"),("s07_research","06","Studio · reel research"),
    ("s08_script","07","Ad script & storyboard"),("s09_ads","08","Static ads, A+ & listings"),
    ("s10_video","09","Promotional video"),("s11_kit","10","Claim guard, tests & kit")]
LIVE={"live_ask":("Live","answered from saved evidence"),"live_brief":("Live","new campaign brief"),
      "live_hindi":("Live","Hindi via Sarvam · 8× speed"),"film_audio":("Generated film","original audio")}
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(channel="chrome")
        pg=await b.new_page(viewport={"width":1920,"height":1080})
        for n in ("title","end"):
            await pg.goto(f"file://{D}/{n}.html"); await pg.wait_for_timeout(600)
            await pg.screenshot(path=f"{D}/{n}.png")
        for key,num,text in CH:
            await pg.goto(f"file://{D}/overlay.html")
            await pg.evaluate("([n,t])=>{document.getElementById('o').innerHTML=`<span class=pill><span class=num>${n}</span>${t}</span>`}", [num,text])
            await pg.wait_for_timeout(150)
            await pg.locator("#o").screenshot(path=f"{D}/ch_{key}.png", omit_background=True)
        for key,(a,bb) in LIVE.items():
            await pg.goto(f"file://{D}/overlay.html")
            await pg.evaluate("([a,b])=>{document.getElementById('o').innerHTML=`<span class=live><span class=dot></span>${a}<small>${b}</small></span>`}", [a,bb])
            await pg.wait_for_timeout(150)
            await pg.locator("#o").screenshot(path=f"{D}/{key}.png", omit_background=True)
        await b.close()
asyncio.run(main())
